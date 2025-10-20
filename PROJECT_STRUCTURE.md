# KBM 2.0 - Project Structure Documentation

## Table of Contents

1. [Overview](#overview)
2. [Root Directory](#root-directory)
3. [Application Modules](#application-modules)
4. [Core Utilities](#core-utilities)
5. [Templates and Static Files](#templates-and-static-files)
6. [Configuration Files](#configuration-files)
7. [Data and Logs](#data-and-logs)
8. [Key Concepts](#key-concepts)
9. [File Reference](#file-reference)

---

## Overview

KBM 2.0 follows a modular Flask application structure with multi-tenant architecture. The application separates concerns into distinct modules (blueprints), uses a master/tenant database pattern, and employs middleware for tenant context management.

### Architecture Pattern

```
┌─────────────────────────────────────────┐
│          User Browser                    │
│   (subdomain.yourdomain.com)            │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│       Nginx Reverse Proxy                │
│   (SSL Termination, Static Files)        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│     Flask Application (Gunicorn)         │
│   ┌─────────────────────────────────┐   │
│   │  Tenant Middleware              │   │
│   │  (Subdomain Detection)          │   │
│   └────────┬────────────────────────┘   │
│            ▼                             │
│   ┌────────────────┬──────────────────┐ │
│   │  Master DB     │  Tenant DB       │ │
│   │  (Accounts,    │  (Keys, Props,   │ │
│   │   Users)       │   Inventory)     │ │
│   └────────────────┴──────────────────┘ │
└─────────────────────────────────────────┘
```

---

## Root Directory

```
KBM2.0/
├── accounts/               # Account signup and management
├── app_admin/             # Application admin interface
├── auth/                  # Authentication (login, logout)
├── checkout/              # Checkout/checkin functionality
├── contacts/              # Contact management
├── exports/               # Data export functionality
├── inventory/             # Core inventory management (keys, lockboxes, signs)
├── kbm_logging/           # Logging utilities
├── main/                  # Main/home page routes
├── middleware/            # Tenant detection middleware
├── migrations/            # Database migrations (unused)
├── migrations_master/     # Master database migrations
├── properties/            # Property and unit management
├── smartlocks/            # Smart lock management
├── static/                # Static assets (CSS, JS, images)
├── templates/             # Jinja2 HTML templates
├── tests/                 # Test files
├── utilities/             # Core utilities (database, tenant manager)
├── KBM2_data/            # Database storage (SQLite files)
├── logs/                  # Application logs
├── app.py                 # Original single-tenant entry point (legacy)
├── app_multitenant.py     # Multi-tenant entry point (MAIN)
├── config.py              # Configuration management
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker build instructions
├── compose.yaml          # Docker Compose configuration
└── setup_multitenant.py  # Database initialization script
```

---

## Application Modules

### 1. accounts/ - Account Management

**Purpose**: Handles tenant account signup and management on the root domain.

**Files**:
- `__init__.py` - Blueprint initialization
- `routes.py` - Account signup, creation

**Key Routes**:
- `/accounts/signup` - Tenant account signup form
- `/accounts/create` - Process account creation

**Database**: Writes to master database (Account table)

**Usage**:
```python
from accounts import accounts_bp
app.register_blueprint(accounts_bp, url_prefix="/accounts")
```

---

### 2. app_admin/ - Application Administration

**Purpose**: Platform administration for managing all tenant accounts (app admin only).

**Files**:
- `__init__.py` - Blueprint initialization
- `views.py` - Admin dashboard, account management, user management

**Key Routes**:
- `/admin` - Admin dashboard
- `/admin/accounts` - List all tenant accounts
- `/admin/accounts/<id>` - View/manage specific account
- `/admin/app-admins` - Manage application administrators

**Access**: Restricted to users with `role='app_admin'`

**Database**: Reads/writes master database

---

### 3. auth/ - Authentication

**Purpose**: User authentication for both root and tenant domains.

**Files**:
- `__init__.py` - Blueprint initialization
- `models.py` - User models (legacy)
- `views.py` - Single-tenant authentication (legacy)
- `views_multitenant.py` - Multi-tenant authentication (ACTIVE)

**Key Routes**:
- `/auth/login` - Login page
- `/auth/logout` - Logout
- `/auth/users` - User management (tenant admins)
- `/auth/users/new` - Create new user
- `/auth/users/<id>/edit` - Edit user

**Authentication Method**: PIN-based (4+ digit numeric code)

**Sessions**: Flask-Login session management

---

### 4. checkout/ - Checkout System

**Purpose**: Check out and check in inventory items.

**Files**:
- `__init__.py` - Blueprint initialization
- `views.py` - Checkout/checkin logic, receipt generation

**Key Routes**:
- `/checkout/start` - Quick checkout/checkin interface
- `/checkout/item/<id>` - Checkout specific item
- `/checkout/checkin/<id>` - Check in item
- `/checkout/<id>/receipt` - View/print receipt

**Features**:
- Quick autocomplete search
- Receipt generation with barcodes
- Activity logging
- Status tracking

**Database**: Tenant database (ItemCheckout table)

---

### 5. contacts/ - Contact Management

**Purpose**: Manage tenant contacts (property owners, vendors, etc.).

**Files**:
- `__init__.py` - Blueprint initialization
- `views.py` - Contact CRUD operations

**Key Routes**:
- `/contacts` - List all contacts
- `/contacts/new` - Create new contact
- `/contacts/<id>` - View contact details
- `/contacts/<id>/edit` - Edit contact
- `/contacts/<id>/delete` - Delete contact

**Contact Types**:
- Tenant
- Owner
- Vendor
- Agent
- Emergency
- Other

**Database**: Tenant database (Contact table)

---

### 6. exports/ - Data Export

**Purpose**: Export inventory data to Excel format.

**Files**:
- `__init__.py` - Blueprint initialization
- `views.py` - Export generation

**Key Routes**:
- `/exports/keys` - Export keys to Excel
- `/exports/lockboxes` - Export lockboxes
- `/exports/signs` - Export signs

**Format**: XLSX files using openpyxl

**Database**: Reads from tenant database

---

### 7. inventory/ - Inventory Management (Core)

**Purpose**: Manage all inventory items (keys, lockboxes, signs).

**Files**:
- `__init__.py` - Blueprint initialization
- `models.py` - Inventory models (legacy)
- `views.py` - Main inventory routes (ACTIVE)
- `import_views.py` - Import functionality

**Key Routes**:

**Keys**:
- `/inventory/keys` - List keys
- `/inventory/keys/new` - Add key
- `/inventory/keys/<id>` - Key details
- `/inventory/keys/<id>/edit` - Edit key
- `/inventory/keys/<id>/delete` - Delete key

**Lockboxes**:
- `/inventory/lockboxes` - List lockboxes
- `/inventory/lockboxes/new` - Add lockbox
- `/inventory/lockboxes/<id>` - Lockbox details

**Signs**:
- `/inventory/signs` - List signs
- `/inventory/signs/new` - Add sign piece
- `/inventory/signs/builder` - Build assembled sign
- `/inventory/signs/<id>/disassemble` - Disassemble sign
- `/inventory/api/available-pieces` - API for available pieces
- `/inventory/signs/<id>/swap-piece/<piece_id>` - Swap sign piece

**Import**:
- `/inventory/import/<type>/upload` - Upload import file
- `/inventory/import/<type>/map` - Map columns
- `/inventory/import/<type>/preview` - Preview import
- `/inventory/import/<type>/execute` - Execute import

**Universal Item Details**:
- `/inventory/item/<id>` - View any item (key, lockbox, sign)

**Database**: Tenant database (Item, ItemCheckout, Activity tables)

---

### 8. main/ - Main Routes

**Purpose**: Home page and core navigation.

**Files**:
- `__init__.py` - Blueprint initialization
- `views.py` - Home page, dashboard

**Key Routes**:
- `/` - Home/dashboard
- `/activity` - Activity log viewer
- `/reports` - Reports page
- `/receipt-lookup` - Look up receipt by ID

**Features**:
- Dashboard with recent activity
- Quick stats
- Navigation hub

---

### 9. middleware/ - Tenant Middleware

**Purpose**: Detect tenant from subdomain and set up database context.

**Files**:
- `__init__.py` - Package initialization
- `tenant_middleware.py` - Middleware implementation

**How It Works**:
1. Intercepts every request
2. Extracts subdomain from request host
3. Looks up tenant account in master database
4. Sets Flask `g.tenant`, `g.subdomain`, `g.is_root_domain`
5. Tenant-specific routes use this context to switch databases

**Usage**: Automatically applied to all requests via `app.before_request`

---

### 10. properties/ - Property Management

**Purpose**: Manage properties and units.

**Files**:
- `__init__.py` - Blueprint initialization
- `views.py` - Property and unit CRUD

**Key Routes**:
- `/properties` - List properties
- `/properties/new` - Add property
- `/properties/<id>` - View property details
- `/properties/<id>/edit` - Edit property
- `/properties/<id>/units/<unit_id>` - Unit details
- `/properties/<id>/units/<unit_id>/edit` - Edit unit
- `/properties/<id>/units/<unit_id>/delete` - Delete unit

**Features**:
- Multi-unit properties
- Address management
- Association with keys/lockboxes

**Database**: Tenant database (Property, PropertyUnit tables)

---

### 11. smartlocks/ - Smart Lock Management

**Purpose**: Manage smart locks with codes.

**Files**:
- `__init__.py` - Blueprint initialization
- `views.py` - Smart lock CRUD

**Key Routes**:
- `/smart-locks` - List smart locks
- `/smart-locks/new` - Add smart lock
- `/smart-locks/<id>` - View details
- `/smart-locks/<id>/edit` - Edit
- `/smart-locks/<id>/delete` - Delete

**Features**:
- Primary and backup codes
- Property/unit associations
- Provider tracking
- Instructions/notes

**Database**: Tenant database (SmartLock table)

---

## Core Utilities

### utilities/ - Core System Utilities

**Purpose**: Shared utilities for database, tenant management, logging.

**Files**:

#### 1. `database.py` - Tenant Database Models

**Purpose**: SQLAlchemy models for tenant-specific data.

**Key Models**:
- `Item` - Base inventory model (keys, lockboxes, signs)
  - Properties: id, type, custom_id, label, status, location, etc.
  - Relationships: checkouts, property, unit, master_key
  - Methods: `generate_custom_id()`, `to_dict()`

- `ItemCheckout` - Checkout records
  - Properties: id, item_id, checked_out_to, checked_out_at, returned_at
  - Methods: `to_dict()`

- `Contact` - Contacts (tenants, owners, vendors)
  - Properties: id, name, type, company, email, phone

- `Property` - Properties
  - Properties: id, name, type, address fields
  - Relationships: units, items

- `PropertyUnit` - Property units
  - Properties: id, property_id, label, notes
  - Relationships: property, items, smartlocks

- `SmartLock` - Smart locks
  - Properties: id, label, provider, code, backup_code

- `Activity` - Activity log
  - Properties: id, action, user_id, target_type, target_id, timestamp

**Database Instance**: `db` (Flask-SQLAlchemy instance)

---

#### 2. `master_database.py` - Master Database Models

**Purpose**: SQLAlchemy models for master (cross-tenant) data.

**Key Models**:
- `Account` - Tenant accounts
  - Properties: id, subdomain, company_name, status, database_path
  - Methods: `to_dict()`

- `MasterUser` - Users (all tenants + app admins)
  - Properties: id, account_id, name, email, role, pin_hash
  - Methods: `set_pin()`, `check_pin()`, `to_dict()`
  - Roles: 'admin', 'staff', 'user', 'app_admin'

**Database Instance**: `master_db` (separate SQLAlchemy instance)

**Important**: Master DB and Tenant DB are completely separate database instances!

---

#### 3. `tenant_manager.py` - Tenant Management

**Purpose**: Manage tenant database connections and switching.

**Key Class**: `TenantManager`

**Methods**:
- `init_app(app)` - Initialize with Flask app
- `get_current_tenant()` - Get current tenant from request context
- `get_tenant_by_subdomain(subdomain)` - Look up tenant by subdomain
- `create_tenant_database(account)` - Create new tenant database
- `get_tenant_session(account)` - Get database session for specific tenant

**How It Works**:
1. Stores reference to Flask app
2. Uses middleware-set `g.tenant` to determine current tenant
3. Creates SQLite database file per tenant
4. Returns scoped session for tenant's database

**Database Path**: `KBM2_data/{subdomain}.db`

---

#### 4. `tenant_helpers.py` - Tenant Database Helpers

**Purpose**: Helper functions for tenant database operations.

**Key Functions**:
- `get_tenant_session()` - Get current tenant's database session
- `tenant_query(model)` - Query current tenant's database
- `tenant_add(obj)` - Add object to current tenant's database
- `tenant_delete(obj)` - Delete object from current tenant's database
- `tenant_commit()` - Commit current tenant's database session
- `tenant_flush()` - Flush current tenant's database session

**Usage Example**:
```python
from utilities.tenant_helpers import tenant_query, tenant_add, tenant_commit

# Query items from current tenant
items = tenant_query(Item).filter_by(type="Key").all()

# Add new item
new_item = Item(type="Key", label="Front Door")
tenant_add(new_item)
tenant_commit()
```

**Why These Exist**: Provides clean abstraction over tenant database operations without directly managing sessions.

---

#### 5. `logger.py` - Logging Configuration

**Purpose**: Configure application logging.

**Usage**:
```python
from utilities.logger import setup_logger
logger = setup_logger(__name__)
logger.info("Something happened")
```

---

### kbm_logging/ - Activity Logging

**Purpose**: Log user actions for audit trail.

**Files**:
- `__init__.py` - Package initialization
- `activity.py` - Activity logging functions

**Key Function**:
```python
def log_activity(action, user, target=None, target_type=None,
                 target_id=None, summary=None, meta=None, commit=True)
```

**Activity Actions**:
- `key_created`, `key_checked_out`, `key_checked_in`, `key_deleted`
- `lockbox_created`, `lockbox_code_changed`
- `sign_created`, `sign_assembled`, `sign_disassembled`, `sign_piece_swapped`
- `property_created`, `contact_created`
- `user_login`, `user_created`

**Database**: Tenant database (Activity table)

**Usage**:
```python
from kbm_logging.activity import log_activity

log_activity(
    action="key_checked_out",
    user=current_user,
    target=key_item,
    summary=f"Checked out {key_item.label} to {person}",
    meta={"person": person, "location": location}
)
```

---

## Templates and Static Files

### templates/ - HTML Templates

**Structure**:
```
templates/
├── base.html                    # Base template with navigation
├── landing.html                 # Root domain landing page
├── 404.html, 403.html, 500.html # Error pages
│
├── accounts/
│   └── signup.html              # Account signup form
│
├── app_admin/
│   ├── dashboard.html           # App admin dashboard
│   ├── accounts.html            # Manage accounts
│   ├── account_detail.html      # Account details
│   └── app_admin_form.html      # Create app admin
│
├── auth/
│   ├── login.html               # Login page
│   ├── users.html               # User list
│   └── user_form.html           # User create/edit
│
├── home.html                    # Tenant home/dashboard
├── activity_logs.html           # Activity log viewer
├── reports.html                 # Reports page
├── receipt_lookup.html          # Receipt lookup
│
├── keys.html                    # Keys list
├── key_add.html                 # Add key form
├── lockboxes.html               # Lockboxes list
├── lockbox_add.html             # Add lockbox form
├── signs.html                   # Signs list
├── sign_add.html                # Add sign form
├── sign_builder.html            # Assembled sign builder
├── item_details.html            # Universal item details
│
├── checkout_start.html          # Quick checkout interface
├── checkout_receipt.html        # Receipt display
│
├── properties.html              # Properties list
├── property_form.html           # Property create/edit
├── property_detail.html         # Property details
├── unit_detail.html             # Unit details
│
├── contacts.html                # Contacts list
├── contact_form.html            # Contact create/edit
├── contact_detail.html          # Contact details
│
├── smartlocks.html              # Smart locks list
├── smartlock_form.html          # Smart lock create/edit
├── smartlock_detail.html        # Smart lock details
│
└── import_*.html                # Import workflow templates
```

**Template Features**:
- Jinja2 template inheritance
- Dark mode support via CSS variables
- Responsive design
- Modal system for forms
- Flash message display
- Context processors for tenant info

**Key Template Variables**:
- `tenant` - Current tenant object
- `current_user` - Logged-in user
- `is_root_domain` - Boolean for root vs tenant domain
- `has_endpoint(name)` - Check if endpoint exists

---

### static/ - Static Assets

**Structure**:
```
static/
├── css/
│   └── style.css              # Main stylesheet
├── js/
│   └── (JavaScript files if any)
└── images/
    └── (Logo, icons, etc.)
```

**CSS Features**:
- CSS variables for theming
- Dark mode support
- Responsive grid layouts
- Card-based design system
- Consistent color palette

**Key CSS Variables**:
```css
:root {
  --color-primary: #e53935;
  --color-accent: #e53935;
  --color-bg: #f5f5f5;
  --color-card: #ffffff;
  --color-text: #1e293b;
  --color-border: #e2e8f0;
  --color-muted: #64748b;
}
```

---

## Configuration Files

### 1. `app_multitenant.py` - Main Application Entry Point

**Purpose**: Creates and configures the Flask application.

**Key Functions**:
- `create_app()` - Application factory
  - Configures master database
  - Initializes tenant manager
  - Registers blueprints
  - Sets up middleware
  - Configures error handlers
  - Defines context processors

**Application Instance**: `app = create_app()`

**Run**:
```bash
python app_multitenant.py
# or
gunicorn app_multitenant:app
```

---

### 2. `config.py` - Configuration Management

**Purpose**: Environment-based configuration.

**Classes**:
- `Config` - Base configuration
- `DevelopmentConfig` - Development settings (DEBUG=True)
- `ProductionConfig` - Production settings
- `TestingConfig` - Testing settings

**Function**:
- `get_config(env)` - Returns config class based on ENV variable

**Environment Variables**:
- `ENV` - Environment name (development/production/testing)
- `SECRET_KEY` - Flask secret key
- `DATABASE_URI` - Database connection string
- `AUTO_CREATE_SCHEMA` - Auto-create database schema (boolean)

---

### 3. `requirements.txt` - Python Dependencies

**Key Dependencies**:
- `Flask==3.1.0` - Web framework
- `Flask-SQLAlchemy==3.1.1` - ORM
- `Flask-Login==0.6.3` - Authentication
- `Flask-Migrate==4.0.7` - Database migrations
- `gunicorn==23.0.0` - Production server
- `openpyxl==3.1.5` - Excel file processing
- `reportlab==4.2.5` - PDF generation
- `python-barcode==0.16.1` - Barcode generation

---

### 4. `.env` Files - Environment Variables

**Files**:
- `.env` - Main environment file (git-ignored)
- `.env.development` - Development settings
- `.env.production` - Production settings

**Format**:
```bash
ENV=production
SECRET_KEY=your-secret-key
DATABASE_URI=sqlite:///path/to/db.db
AUTO_CREATE_SCHEMA=false
```

---

### 5. `Dockerfile` - Docker Build Instructions

**Purpose**: Multi-stage Docker build for production.

**Stages**:
1. **base** - Python 3.11 slim base image
2. **builder** - Installs dependencies in virtual environment
3. **final** - Minimal runtime image

**Key Features**:
- Non-root user (`appuser`)
- Virtual environment
- Health check support
- Persistent volumes for data

---

### 6. `compose.yaml` - Docker Compose Configuration

**Purpose**: Orchestrate Docker containers.

**Services**:
- `kbm-app` - Main application container

**Volumes**:
- `kbm-data` - Database files
- `kbm-logs` - Log files

---

## Data and Logs

### KBM2_data/ - Database Storage

**Purpose**: Store all SQLite database files.

**Files**:
- `master.db` - Master database (accounts, users)
- `{subdomain}.db` - Tenant database per account

**Structure**:
```
KBM2_data/
├── master.db           # Master database
├── vesta.db           # Tenant: vesta
├── acme.db            # Tenant: acme
└── ...
```

**Backup**: This entire directory should be backed up regularly!

---

### logs/ - Application Logs

**Purpose**: Store application logs.

**Files**:
- `app.log` - Application log
- `error.log` - Error log
- `access.log` - Access log (if configured)

---

## Key Concepts

### Multi-Tenant Architecture

**What It Is**: Single application instance serves multiple isolated customers (tenants).

**How It Works**:
1. Each tenant has a unique subdomain (e.g., vesta.example.com)
2. Middleware detects subdomain and loads tenant context
3. Separate database per tenant ensures data isolation
4. Master database manages accounts and users across all tenants

**Benefits**:
- Complete data isolation
- Easy tenant provisioning
- Scalable architecture
- Simplified deployment (one app, many customers)

---

### Database Separation

**Master Database** (`master.db`):
- Stores: Accounts, All Users (cross-tenant)
- Used by: Signup, app admin, authentication
- Schema: Account, MasterUser tables

**Tenant Databases** (`{subdomain}.db`):
- Stores: Items, Properties, Contacts, Activity (tenant-specific)
- Used by: All inventory, checkout, property management
- Schema: Item, Property, Contact, Activity, etc.
- Isolation: Each tenant's data in separate database file

**Why This Design**:
- Security: Tenant data physically separated
- Performance: Smaller databases per tenant
- Scalability: Easy to move tenant databases to different servers
- Simplicity: No complex row-level security

---

### Request Flow

1. **User visits**: `https://vesta.example.com/inventory/keys`

2. **Nginx receives request**:
   - Terminates SSL
   - Serves static files directly
   - Proxies to Gunicorn

3. **Tenant Middleware**:
   - Extracts subdomain: "vesta"
   - Looks up Account in master DB
   - Sets `g.tenant` = Account object
   - Sets `g.subdomain` = "vesta"

4. **View Function**:
   ```python
   @inventory_bp.route('/keys')
   @login_required
   @tenant_required  # Decorator checks g.tenant exists
   def list_keys():
       # Use tenant helpers to access tenant DB
       keys = tenant_query(Item).filter_by(type="Key").all()
       return render_template('keys.html', keys=keys)
   ```

5. **Template Rendering**:
   - Access `tenant` variable for tenant info
   - Render HTML with tenant-specific data

6. **Response**:
   - HTML returned to Nginx
   - Nginx adds security headers
   - Response sent to user browser

---

### Authentication Flow

1. **User visits tenant domain**: `https://vesta.example.com`
2. **Not logged in**: Redirected to `/auth/login`
3. **Login form**: Enter email and PIN
4. **Submit**:
   - Look up MasterUser in master DB by email
   - Verify account_id matches current tenant
   - Check PIN hash
   - Create Flask-Login session
5. **Logged in**: Redirect to home page
6. **Session**: Stored in encrypted cookie
7. **Subsequent requests**: Flask-Login loads user from session

---

## File Reference

### Key Files Explained

| File | Purpose | Important? |
|------|---------|------------|
| `app_multitenant.py` | Main entry point | ⭐⭐⭐ Critical |
| `config.py` | Configuration management | ⭐⭐⭐ Critical |
| `requirements.txt` | Python dependencies | ⭐⭐⭐ Critical |
| `utilities/database.py` | Tenant DB models | ⭐⭐⭐ Critical |
| `utilities/master_database.py` | Master DB models | ⭐⭐⭐ Critical |
| `utilities/tenant_manager.py` | Tenant switching | ⭐⭐⭐ Critical |
| `utilities/tenant_helpers.py` | DB helper functions | ⭐⭐⭐ Critical |
| `middleware/tenant_middleware.py` | Subdomain detection | ⭐⭐⭐ Critical |
| `inventory/views.py` | Inventory routes | ⭐⭐ Important |
| `auth/views_multitenant.py` | Authentication | ⭐⭐ Important |
| `setup_multitenant.py` | DB initialization | ⭐⭐ Important |
| `Dockerfile` | Docker build | ⭐⭐ Important |
| `compose.yaml` | Docker orchestration | ⭐⭐ Important |
| `templates/base.html` | Base template | ⭐ Nice to have |
| `static/css/style.css` | Styling | ⭐ Nice to have |

---

### Configuration Priority

Configuration is loaded in this order (later overrides earlier):

1. `config.py` defaults
2. `.env` file (if exists)
3. `ENV_FILE` specified file (if set)
4. Environment variables (highest priority)

**Example**:
```bash
# .env
SECRET_KEY=default-secret

# .env.production
SECRET_KEY=production-secret

# If ENV_FILE=.env.production, production-secret is used
```

---

### Database Schema

**Master Database Tables**:
```sql
accounts (
    id INTEGER PRIMARY KEY,
    subdomain TEXT UNIQUE,
    company_name TEXT,
    contact_email TEXT,
    status TEXT,
    database_path TEXT,
    created_at DATETIME
)

master_users (
    id INTEGER PRIMARY KEY,
    account_id INTEGER,  -- NULL for app admins
    name TEXT,
    email TEXT UNIQUE,
    role TEXT,
    pin_hash TEXT,
    is_active BOOLEAN,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
)
```

**Tenant Database Tables**:
```sql
items (
    id INTEGER PRIMARY KEY,
    type TEXT,  -- 'Key', 'Lockbox', 'Sign'
    custom_id TEXT,
    label TEXT,
    status TEXT,
    location TEXT,
    property_id INTEGER,
    property_unit_id INTEGER,
    master_key_id INTEGER,
    parent_sign_id INTEGER,
    sign_subtype TEXT,
    piece_type TEXT,
    -- Many more fields...
)

properties (
    id INTEGER PRIMARY KEY,
    name TEXT,
    type TEXT,
    address_line1 TEXT,
    -- Address fields...
)

property_units (
    id INTEGER PRIMARY KEY,
    property_id INTEGER,
    label TEXT,
    FOREIGN KEY (property_id) REFERENCES properties(id)
)

contacts (
    id INTEGER PRIMARY KEY,
    name TEXT,
    contact_type TEXT,
    company TEXT,
    email TEXT,
    phone TEXT,
    user_id INTEGER  -- Reference to MasterUser ID (not FK)
)

item_checkouts (
    id INTEGER PRIMARY KEY,
    item_id INTEGER,
    checked_out_to TEXT,
    checked_out_at DATETIME,
    returned_at DATETIME,
    FOREIGN KEY (item_id) REFERENCES items(id)
)

smart_locks (
    id INTEGER PRIMARY KEY,
    label TEXT,
    provider TEXT,
    code TEXT,
    backup_code TEXT,
    property_id INTEGER,
    property_unit_id INTEGER
)

activities (
    id INTEGER PRIMARY KEY,
    action TEXT,
    user_id INTEGER,  -- Reference to MasterUser ID (not FK)
    target_type TEXT,
    target_id INTEGER,
    summary TEXT,
    meta JSON,
    timestamp DATETIME
)
```

**Important Note**: Tenant tables don't have foreign keys to master database tables (like user_id). They store IDs only. This is intentional for database separation.

---

### Common Patterns

#### 1. Creating a New Blueprint Module

```python
# mymodule/__init__.py
from flask import Blueprint

mymodule_bp = Blueprint('mymodule', __name__)

from . import views
```

```python
# mymodule/views.py
from . import mymodule_bp
from flask import render_template
from flask_login import login_required
from middleware.tenant_middleware import tenant_required

@mymodule_bp.route('/myroute')
@login_required
@tenant_required
def my_view():
    return render_template('my_template.html')
```

```python
# app_multitenant.py
from mymodule import mymodule_bp
app.register_blueprint(mymodule_bp, url_prefix='/mymodule')
```

#### 2. Accessing Tenant Database

```python
from utilities.tenant_helpers import tenant_query, tenant_add, tenant_commit
from utilities.database import Item

# Query
items = tenant_query(Item).filter_by(type="Key").all()

# Add
new_item = Item(type="Key", label="Test")
tenant_add(new_item)
tenant_commit()

# Update
item = tenant_query(Item).filter_by(id=1).first()
item.label = "Updated"
tenant_commit()

# Delete
from utilities.tenant_helpers import tenant_delete
tenant_delete(item)
tenant_commit()
```

#### 3. Logging Activity

```python
from kbm_logging.activity import log_activity
from flask_login import current_user

log_activity(
    action="item_created",
    user=current_user,
    target=item,
    summary=f"Created {item.type} '{item.label}'",
    meta={"item_type": item.type}
)
```

---

### Deployment Artifacts

**Required for Production**:
- [x] `app_multitenant.py` - Main app
- [x] `config.py` - Configuration
- [x] `requirements.txt` - Dependencies
- [x] All module directories
- [x] `templates/` directory
- [x] `static/` directory
- [x] `utilities/` directory
- [x] `middleware/` directory
- [x] `Dockerfile` - Docker build
- [x] `compose.yaml` - Docker Compose
- [ ] `entrypoint.sh` - **MISSING, NEED TO CREATE**
- [x] `.env.production` - Production config
- [x] `.dockerignore` - Docker ignore rules

**Not Required**:
- `app.py` - Legacy single-tenant
- `auth/views.py` - Legacy auth
- `tests/` - Test files (but good to have)
- `.git/` - Git history
- `venv/`, `.venv/` - Virtual environments
- `__pycache__/` - Python cache

---

## Summary

The KBM 2.0 project is a well-structured Flask application with:

1. **Clear Separation**: Master/tenant database separation
2. **Modular Design**: Blueprint-based modules
3. **Security**: Data isolation per tenant
4. **Scalability**: Easy to add tenants, deploy to multiple servers
5. **Maintainability**: Clean code structure, helper functions

**Core Flow**: Request → Nginx → Gunicorn → Middleware (detect tenant) → View (use tenant DB) → Template → Response

**Database Pattern**: Master DB (accounts, users) + Tenant DBs (operations data)

**Authentication**: PIN-based with Flask-Login sessions

**Key Files to Know**:
- `app_multitenant.py` - Entry point
- `utilities/tenant_manager.py` - Tenant switching
- `utilities/tenant_helpers.py` - DB operations
- `middleware/tenant_middleware.py` - Subdomain detection

---

**Document Version**: 1.0
**Last Updated**: 2025-10-20
**Author**: Claude (Anthropic)
**Project**: KBM 2.0 Multi-Tenant Application
