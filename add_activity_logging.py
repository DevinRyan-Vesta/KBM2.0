#!/usr/bin/env python3
"""Add activity logging to property and smartlock creation"""

# Fix 1: Add logging to property creation
print("Fixing property creation logging...")
properties_path = "properties/views.py"
with open(properties_path, 'r', encoding='utf-8') as f:
    properties_content = f.read()

# Check if log_activity is imported
if 'from utilities.database import' in properties_content:
    # Find the import line and add log_activity if not there
    if 'log_activity' not in properties_content[:1000]:  # Check imports section
        properties_content = properties_content.replace(
            'from utilities.database import db, Property, PropertyUnit',
            'from utilities.database import db, Property, PropertyUnit, log_activity'
        )
        print("[OK] Added log_activity import to properties/views.py")
else:
    print("[WARN] Could not find database import in properties/views.py")

# Add logging after property creation
old_property_create = '''        tenant_add(property_obj)
        tenant_commit()
        flash("Property created.", "success")'''

new_property_create = '''        tenant_add(property_obj)
        tenant_flush()
        log_activity(
            "property_created",
            user=current_user,
            target=property_obj,
            summary=f"Created property {name}",
            meta={
                "name": name,
                "type": property_type,
                "address": address_line1,
                "city": city,
                "state": state,
            },
        )
        tenant_commit()
        flash("Property created.", "success")'''

if old_property_create in properties_content:
    properties_content = properties_content.replace(old_property_create, new_property_create)
    print("[OK] Added activity logging to property creation")
else:
    print("[WARN] Could not find property creation code to modify")

# Also need to import current_user if not already
if 'from flask_login import' in properties_content and 'current_user' not in properties_content[:500]:
    properties_content = properties_content.replace(
        'from flask_login import login_required',
        'from flask_login import login_required, current_user'
    )
    print("[OK] Added current_user import to properties/views.py")

# Also need to import tenant_flush
if 'tenant_flush' not in properties_content[:1000]:
    properties_content = properties_content.replace(
        'from utilities.tenant_helpers import tenant_query, tenant_add, tenant_commit',
        'from utilities.tenant_helpers import tenant_query, tenant_add, tenant_commit, tenant_flush'
    )
    print("[OK] Added tenant_flush import to properties/views.py")

with open(properties_path, 'w', encoding='utf-8') as f:
    f.write(properties_content)

print("\n" + "="*50)

# Fix 2: Add logging to smartlock creation
print("Fixing smartlock creation logging...")
smartlocks_path = "smartlocks/views.py"
with open(smartlocks_path, 'r', encoding='utf-8') as f:
    smartlocks_content = f.read()

# Check if log_activity is imported
if 'from utilities.database import' in smartlocks_content:
    if 'log_activity' not in smartlocks_content[:1000]:
        smartlocks_content = smartlocks_content.replace(
            'from utilities.database import db, SmartLock, Property, PropertyUnit',
            'from utilities.database import db, SmartLock, Property, PropertyUnit, log_activity'
        )
        print("[OK] Added log_activity import to smartlocks/views.py")
else:
    print("[WARN] Could not find database import in smartlocks/views.py")

# Find and replace the smartlock creation
# This is trickier because we need to find the exact location
if 'tenant_add(smartlock)' in smartlocks_content and 'tenant_commit()' in smartlocks_content:
    # Use regex to find and replace the section
    import re

    # Pattern to match the smartlock creation and commit
    pattern = r'(smartlock = SmartLock\([^)]+\))\s+(tenant_add\(smartlock\))\s+(tenant_commit\(\))'

    replacement = r'\1\n        \2\n        tenant_flush()\n        log_activity(\n            "smartlock_created",\n            user=current_user,\n            target=smartlock,\n            summary=f"Created smart lock {label}",\n            meta={\n                "label": label,\n                "code": code,\n                "provider": provider,\n                "property_id": property_ref.id if property_ref else None,\n            },\n        )\n        \3'

    if re.search(pattern, smartlocks_content, re.DOTALL):
        smartlocks_content = re.sub(pattern, replacement, smartlocks_content, flags=re.DOTALL)
        print("[OK] Added activity logging to smartlock creation")
    else:
        print("[WARN] Could not find smartlock creation pattern to modify")

# Add imports if needed
if 'from flask_login import' in smartlocks_content and 'current_user' not in smartlocks_content[:500]:
    smartlocks_content = smartlocks_content.replace(
        'from flask_login import login_required',
        'from flask_login import login_required, current_user'
    )
    print("[OK] Added current_user import to smartlocks/views.py")

if 'tenant_flush' not in smartlocks_content[:1000]:
    smartlocks_content = smartlocks_content.replace(
        'from utilities.tenant_helpers import tenant_query, tenant_add, tenant_commit, get_tenant_session',
        'from utilities.tenant_helpers import tenant_query, tenant_add, tenant_commit, tenant_flush, get_tenant_session'
    )
    print("[OK] Added tenant_flush import to smartlocks/views.py")

with open(smartlocks_path, 'w', encoding='utf-8') as f:
    f.write(smartlocks_content)

print("\n[OK] Activity logging fixes complete!")
print("Property and smart lock creation will now be logged in activity logs.")
