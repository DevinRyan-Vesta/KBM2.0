# KBM Multi-Tenant Architecture

This document explains the multi-tenant architecture implementation for the Key & Lockbox Management (KBM) system.

## Overview

The KBM application now supports **multi-tenancy** where:
- Each company gets its own **subdomain** (e.g., `vesta.example.com`)
- Each company has its own **isolated database** (separate SQLite file)
- Users can only access their company's data
- App administrators can manage all accounts without accessing tenant data

## Architecture

### Database Structure

#### Master Database (`KBM2_data/master.db`)
Stores system-level data:
- **Accounts**: Company/tenant information (subdomain, status, etc.)
- **MasterUsers**: All user authentication (across all tenants)
- **Invitations**: User invitation tokens

#### Tenant Databases (`KBM2_data/tenants/{subdomain}.db`)
Each tenant gets their own database containing:
- Items (keys, lockboxes, signs)
- Checkouts and assignments
- Contacts
- Properties and units
- Smart locks
- Activity logs

### Request Flow

1. **Request arrives** → Extract subdomain from host header
2. **Middleware checks** → Look up account in master database
3. **Set tenant context** → Load appropriate tenant database
4. **Process request** → Use tenant-specific data
5. **Return response** → Data isolated to that tenant

```
Request: vesta.example.com/items
    ↓
Middleware extracts subdomain: "vesta"
    ↓
Load Account(subdomain="vesta")
    ↓
Connect to KBM2_data/tenants/vesta.db
    ↓
Query items from vesta's database
    ↓
Return vesta's items only
```

## Setup Instructions

### Initial Setup

1. **Run the setup script**:
   ```bash
   python setup_multitenant.py
   ```

   This will:
   - Create the master database
   - Create your first app admin account
   - Optionally create a demo tenant

2. **Start the application**:
   ```bash
   python app_multitenant.py
   ```

3. **Access the application**:
   - Root domain: `http://localhost:5000`
   - App admin: `http://localhost:5000/auth/login`
   - Tenant: `http://{subdomain}.localhost:5000`

### Local Development

For local development with subdomains:
- Use `subdomain.localhost` format (most browsers support this)
- Example: `vesta.localhost:5000`, `acme.localhost:5000`
- No `/etc/hosts` modification needed

### Creating Accounts

#### Via Signup Form (Self-Service)
1. Visit `http://localhost:5000/accounts/signup`
2. Fill in company details and admin user info
3. Choose a unique subdomain
4. Submit to create account and database
5. Redirect to new tenant subdomain

#### Via App Admin Dashboard
1. Login as app admin
2. Use the dashboard to manually create accounts
3. Set initial user credentials

## User Roles

### App Admin (`app_admin`)
- Access: Root domain only
- Can view all accounts
- Can activate/suspend/delete accounts
- **Cannot** access tenant data directly
- Manages system-level settings

### Tenant Admin (`admin`)
- Access: Their company's subdomain only
- Full access to their company's data
- Can invite/manage users in their company
- Can export reports

### Tenant User (`user`)
- Access: Their company's subdomain only
- Can view and manage items
- Cannot manage users or settings

## Key Components

### 1. Master Database Models (`utilities/master_database.py`)
- `Account`: Company/tenant records
- `MasterUser`: User authentication (all users)
- `Invitation`: User invitations

### 2. Tenant Manager (`utilities/tenant_manager.py`)
- `TenantManager`: Handles database connections
- `create_tenant_database()`: Creates new tenant DB
- `get_tenant_session()`: Gets active session
- `set_tenant_context()`: Sets Flask g.tenant

### 3. Tenant Middleware (`middleware/tenant_middleware.py`)
- `TenantMiddleware`: Request interceptor
- `@tenant_required`: Decorator for tenant-only routes
- `@root_domain_only`: Decorator for root-only routes
- `@app_admin_required`: Decorator for app admin routes

### 4. Blueprints

#### Root Domain Blueprints
- `accounts_bp`: Account signup and creation
- `app_admin_bp`: App admin dashboard and management
- `auth_bp`: Login/logout (works on both root and tenant)

#### Tenant Domain Blueprints
- `main_bp`: Home dashboard
- `inventory_bp`: Item management
- `checkout_bp`: Check-in/check-out
- `contacts_bp`: Contact management
- `properties_bp`: Property management
- `smartlocks_bp`: Smart lock management
- `exports_bp`: Data export

## Usage Examples

### Accessing the System

**As App Admin:**
```
1. Go to http://localhost:5000/auth/login
2. Enter your PIN
3. Access admin dashboard
```

**As Tenant User:**
```
1. Go to http://vesta.localhost:5000
2. Enter your PIN
3. Access company dashboard
```

### Creating a New Account

**Programmatically:**
```python
from app_multitenant import app
from utilities.master_database import master_db, Account, MasterUser
from utilities.tenant_manager import tenant_manager

with app.app_context():
    # Create account
    account = Account(
        subdomain='newcompany',
        company_name='New Company LLC',
        status='active'
    )
    account.database_path = str(tenant_manager.get_tenant_database_path(account))
    master_db.session.add(account)
    master_db.session.flush()

    # Create tenant database
    tenant_manager.create_tenant_database(account)

    # Create admin user
    admin = MasterUser(
        account_id=account.id,
        name='Admin User',
        email='admin@newcompany.com',
        role='admin'
    )
    admin.set_pin('1234')
    master_db.session.add(admin)
    master_db.session.commit()
```

### Querying Tenant Data

**In a route handler:**
```python
from flask import g
from utilities.tenant_manager import tenant_manager
from utilities.database import Item

@app.route('/items')
@tenant_required
def list_items():
    # Get current tenant's session
    session = tenant_manager.get_current_session()

    # Query items from tenant database
    items = session.query(Item).all()

    return render_template('items.html', items=items)
```

## Production Deployment

### DNS Configuration

Configure wildcard DNS for your domain:
```
A    example.com         → your_server_ip
A    *.example.com       → your_server_ip
```

### Application Configuration

Update `config.py`:
```python
class ProductionConfig(Config):
    SERVER_NAME = 'example.com'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///path/to/master.db'
    # ... other settings
```

### WSGI Server

Use gunicorn or similar:
```bash
gunicorn -w 4 -b 0.0.0.0:8000 app_multitenant:app
```

### Reverse Proxy (nginx)

```nginx
server {
    listen 80;
    server_name example.com *.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Security Considerations

1. **Data Isolation**: Each tenant has a separate database file
2. **Authentication**: Users can only log in to their assigned account
3. **Authorization**: Middleware prevents cross-tenant data access
4. **App Admin Access**: App admins cannot directly access tenant data
5. **PIN Security**: All PINs are hashed using werkzeug.security

## Troubleshooting

### Subdomain not working locally

**Problem**: `vesta.localhost` returns 404
**Solution**:
- Most modern browsers support `*.localhost` automatically
- Ensure you're using `http://` (not `https://`) locally
- Try `vesta.lvh.me:5000` as an alternative (resolves to 127.0.0.1)

### Database not found

**Problem**: "Tenant database not found"
**Solution**:
- Run `setup_multitenant.py` to create accounts
- Check that `KBM2_data/tenants/{subdomain}.db` exists
- Verify account status is 'active' in master database

### Cannot log in

**Problem**: "Invalid PIN"
**Solution**:
- Verify you're on the correct subdomain
- App admins must use root domain (`localhost:5000`)
- Tenant users must use their subdomain (`vesta.localhost:5000`)
- Check user's `account_id` matches the current tenant

## Migration from Single-Tenant

To migrate from the original single-tenant app:

1. **Backup your data**: Copy your current `app.db`
2. **Run setup**: `python setup_multitenant.py`
3. **Create a tenant account** for your existing data
4. **Copy database**:
   ```bash
   cp app.db KBM2_data/tenants/yourcompany.db
   ```
5. **Migrate users**: Create MasterUser records for existing users
6. **Test**: Access via `http://yourcompany.localhost:5000`

## Files Changed/Added

### New Files
- `utilities/master_database.py` - Master DB models
- `utilities/tenant_manager.py` - Tenant connection manager
- `middleware/tenant_middleware.py` - Subdomain routing
- `accounts/` - Account signup blueprint
- `app_admin/` - App admin dashboard
- `auth/views_multitenant.py` - Updated auth for multi-tenancy
- `app_multitenant.py` - Multi-tenant app entry point
- `setup_multitenant.py` - Setup script
- `templates/accounts/signup.html` - Signup form
- `templates/app_admin/` - Admin templates
- `templates/auth/login.html` - Updated login
- `templates/landing.html` - Root domain landing

### Modified Approach
- Old `app.py` remains for single-tenant use
- New `app_multitenant.py` for multi-tenant
- Existing blueprints work with both (via decorators)

## Support

For questions or issues:
1. Check this documentation
2. Review the code comments
3. Test with debug mode enabled
4. Check Flask/SQLAlchemy logs

## Future Enhancements

Potential improvements:
- [ ] User invitation system (partially implemented)
- [ ] Account billing/quotas
- [ ] PostgreSQL support (vs SQLite)
- [ ] Account usage analytics
- [ ] Tenant data export/backup
- [ ] SSO/OAuth integration
- [ ] Custom branding per tenant
