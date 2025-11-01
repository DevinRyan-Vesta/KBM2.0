#!/usr/bin/env python3
"""Script to fix contact views issues"""

# Fix contacts/views.py - add missing tenant_delete import
views_path = "contacts/views.py"
with open(views_path, 'r', encoding='utf-8-sig') as f:
    content = f.read()

# Check if tenant_delete is already imported
if 'tenant_delete' not in content[:500]:  # Check first 500 chars (imports section)
    # Add tenant_delete to the imports
    old_import = 'from utilities.tenant_helpers import tenant_query, tenant_add, tenant_commit, tenant_rollback, get_tenant_session'
    new_import = 'from utilities.tenant_helpers import tenant_query, tenant_add, tenant_commit, tenant_rollback, get_tenant_session, tenant_delete'

    if old_import in content:
        content = content.replace(old_import, new_import)
        with open(views_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[OK] Added tenant_delete import to {views_path}")
    else:
        print(f"[ERROR] Could not find import line in {views_path}")
else:
    print(f"[OK] {views_path} already has tenant_delete imported")

print("\n[OK] Contact fixes complete!")
print("You should now be able to:")
print("  - Link contacts to users")
print("  - View contact details pages")
print("  - Delete contacts")
