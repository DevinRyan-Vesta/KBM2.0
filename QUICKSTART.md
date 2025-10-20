# Multi-Tenant KBM Quick Start Guide

## 🚀 Getting Started in 3 Minutes

### Step 1: Setup Test Data (Already Done!)
```bash
python test_multitenant.py
```

This creates:
- Master database with app admin
- Demo tenant account
- Test users

### Step 2: Start the Server
```bash
python app_multitenant.py
```

Server starts on `http://localhost:5000`

### Step 3: Test It!

#### Option A: Use Demo Account (Fastest)
1. Open browser: `http://demo.localhost:5000`
2. Enter PIN: `5678`
3. ✅ You're in!

#### Option B: Create New Account
1. Open browser: `http://localhost:5000/accounts/signup`
2. Fill in your company details
3. Choose a subdomain (e.g., "mycompany")
4. Submit
5. Access at: `http://mycompany.localhost:5000`

## 📋 Test Credentials

### Demo Tenant
- **URL:** http://demo.localhost:5000
- **Email:** admin@demo.com
- **PIN:** 5678

### App Admin
- **URL:** http://localhost:5000/auth/login
- **Email:** admin@test.com
- **PIN:** 1234

## 🎯 What Works Now

✅ **Account Creation** - Create new company accounts with own database
✅ **Subdomain Routing** - Each company gets their own subdomain
✅ **Authentication** - Login with PIN, tenant-specific
✅ **Database Isolation** - Completely separate data per company
✅ **Main Dashboard** - View stats (once logged in to tenant)

## ⚙️ What Needs Updating

The following pages will load but may have database errors until updated:
- `/inventory/*` - Item management
- `/checkout/*` - Check-in/out
- `/contacts/*` - Contacts
- `/properties/*` - Properties
- `/smart-locks/*` - Smart locks

**Why?** These blueprints still use single-tenant database queries and need conversion to multi-tenant queries.

## 🔧 How to Update a Blueprint

Example for `inventory/views.py`:

**Before:**
```python
from utilities.database import db, Item

items = Item.query.all()
db.session.add(new_item)
db.session.commit()
```

**After:**
```python
from utilities.tenant_helpers import tenant_query, tenant_add, tenant_commit
from middleware.tenant_middleware import tenant_required

@inventory_bp.route('/items')
@login_required
@tenant_required  # Add this decorator!
def list_items():
    items = tenant_query(Item).all()  # Use tenant_query
    # ... rest of code
```

## 📁 File Structure

```
KBM2_data/
  ├── master.db              # All accounts & users
  └── tenants/
      ├── demo.db           # Demo company data
      ├── vesta.db          # Vesta company data
      └── [subdomain].db    # Each company gets own DB
```

## 🌐 URLs Explained

| URL | What It Does |
|-----|--------------|
| `localhost:5000` | Root domain (signup/app admin) |
| `localhost:5000/accounts/signup` | Create new company |
| `demo.localhost:5000` | Demo company login |
| `[your].localhost:5000` | Your company's site |

## 🐛 Troubleshooting

### "Account not found" error
- Make sure you're using `.localhost` (e.g., `demo.localhost:5000`)
- Check the subdomain exists in master database

### Database errors on inventory/checkout pages
- Normal! These blueprints aren't updated yet
- They still work in single-tenant mode (old `app.py`)

### Can't access `subdomain.localhost`
- Some browsers don't support this - try Firefox or Chrome
- Alternative: use `subdomain.lvh.me:5000` (resolves to 127.0.0.1)

## 📝 Testing Checklist

- [ ] Server starts without errors
- [ ] Can access signup page
- [ ] Can create a new account
- [ ] Can login to demo tenant
- [ ] Dashboard loads for tenant
- [ ] Can create app admin account
- [ ] Multiple tenants work simultaneously

## 🎓 Architecture Overview

```
Request: vesta.localhost:5000/items
    ↓
[Middleware] Extract subdomain: "vesta"
    ↓
[Middleware] Load Account(subdomain="vesta")
    ↓
[Middleware] Connect to tenants/vesta.db
    ↓
[Route Handler] Query items from vesta's DB
    ↓
[Response] Return vesta's items only
```

## Next Steps

1. **Test the demo account** - Verify multi-tenancy works
2. **Create your own account** - Test full signup workflow
3. **Update blueprints** - Make all features multi-tenant
4. **Add your team** - Test user management
5. **Deploy** - Take it to production!

## 💡 Pro Tips

- Each tenant is completely isolated - can't see other tenants' data
- You (as app admin) can see all accounts but not their data
- Users can only login to their assigned company
- Subdomains are validated (alphanumeric + hyphens only)
- First user becomes admin automatically

## Need Help?

Check these files:
- `MULTITENANT_README.md` - Complete architecture guide
- `TESTING_RESULTS.md` - What's tested and working
- `test_multitenant.py` - Setup script
- `utilities/tenant_helpers.py` - Database helper functions

---

**Status:** Core infrastructure ✅ WORKING
**Next:** Update remaining blueprints for full functionality
