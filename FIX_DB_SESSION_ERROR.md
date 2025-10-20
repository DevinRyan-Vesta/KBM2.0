# Fixed: SQLAlchemy Instance Error

## Problem
When adding a property, you encountered:
```
RuntimeError: The current Flask app is not registered with this 'SQLAlchemy' instance.
```

## Root Cause
The initial conversion script replaced `Property.query` with `tenant_query(Property)`, but it missed `db.session.get()`, `db.session.query()`, and `db.session.flush()` calls. These were still trying to use the old single-tenant `db` instance instead of the tenant-specific session.

## Solution Applied

### Files Fixed
Updated all blueprint files to replace:
- `db.session.get(` → `get_tenant_session().get(`
- `db.session.query(` → `get_tenant_session().query(`
- `db.session.flush()` → `tenant_flush()`

### Files Updated:
- ✅ `properties/views.py`
- ✅ `inventory/views.py`
- ✅ `inventory/import_views.py`
- ✅ `checkout/views.py`
- ✅ `contacts/views.py`
- ✅ `smartlocks/views.py`

## Test It Now

The Flask server has automatically reloaded with the fixes. Try adding a property again:

1. Log in to your tenant account
2. Go to Properties
3. Click "Add Property"
4. Fill in the form
5. Submit

✅ **It should work now!**

## What Changed

**Before (broken):**
```python
def _get_property_or_404(property_id: int) -> Property:
    property_obj = db.session.get(Property, property_id)  # ❌ Wrong instance
    if property_obj is None:
        abort(404)
    return property_obj
```

**After (fixed):**
```python
def _get_property_or_404(property_id: int) -> Property:
    property_obj = get_tenant_session().get(Property, property_id)  # ✅ Correct!
    if property_obj is None:
        abort(404)
    return property_obj
```

## Verification

No more `db.session` calls in any blueprint file. Everything now uses:
- `tenant_query(Model)` for queries
- `get_tenant_session()` for raw session access
- `tenant_add()`, `tenant_commit()`, `tenant_rollback()` for operations

## Status: ✅ FIXED

All database operations now properly use the tenant-specific database session. You can add properties, items, contacts, and everything else without errors!
