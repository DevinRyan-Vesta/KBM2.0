#!/usr/bin/env python3
"""
Automatically convert blueprint views to multi-tenant.
Updates database queries to use tenant-aware sessions.
"""

import os
import re
from pathlib import Path


def convert_file_to_multitenant(file_path: Path) -> bool:
    """
    Convert a Python views file to use tenant-aware queries.

    Returns:
        True if file was modified, False otherwise
    """
    print(f"Processing: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    modified = False

    # Check if already converted
    if 'tenant_helpers import' in content or '@tenant_required' in content:
        print(f"  [SKIP] Already converted")
        return False

    # Add imports at the top if needed
    if 'from utilities.database import' in content:
        # Add tenant helpers import
        if 'from utilities.tenant_helpers import' not in content:
            content = content.replace(
                'from utilities.database import',
                'from utilities.tenant_helpers import tenant_query, tenant_add, tenant_commit, tenant_rollback, tenant_delete, tenant_flush, get_tenant_session\n' +
                'from middleware.tenant_middleware import tenant_required\n' +
                'from utilities.database import'
            )
            modified = True
            print("  [+] Added tenant imports")
        elif 'tenant_delete' not in content or 'tenant_flush' not in content:
            # Update existing import to include missing helpers
            content = re.sub(
                r'from utilities\.tenant_helpers import ([^\n]+)',
                r'from utilities.tenant_helpers import tenant_query, tenant_add, tenant_commit, tenant_rollback, tenant_delete, tenant_flush, get_tenant_session',
                content
            )
            modified = True
            print("  [+] Updated tenant imports")

    # Add @tenant_required decorator to routes
    # Find all route functions
    route_pattern = r'(@\w+_bp\.route\([^\)]+\)(?:\s*@\w+)*\s*\n)(def \w+\([^\)]*\):)'

    def add_tenant_decorator(match):
        decorators = match.group(1)
        func_def = match.group(2)

        # Skip if already has tenant_required
        if '@tenant_required' in decorators:
            return match.group(0)

        # Skip if it's a debug route or doesn't need tenant context
        if 'debug_' in func_def or '_api' in func_def:
            return match.group(0)

        # Add @tenant_required before function definition
        return decorators + '@tenant_required\n' + func_def

    new_content = re.sub(route_pattern, add_tenant_decorator, content, flags=re.MULTILINE)
    if new_content != content:
        content = new_content
        modified = True
        print("  [+] Added @tenant_required decorators")

    # Convert Item.query to tenant_query(Item)
    content = re.sub(r'\bItem\.query\b', 'tenant_query(Item)', content)

    # Convert other model queries
    for model in ['User', 'ItemCheckout', 'Contact', 'Property', 'PropertyUnit', 'SmartLock', 'ActivityLog']:
        content = re.sub(rf'\b{model}\.query\b', f'tenant_query({model})', content)

    # Convert db.session.add to tenant_add
    content = re.sub(r'\bdb\.session\.add\(', 'tenant_add(', content)

    # Convert db.session.commit() to tenant_commit()
    content = re.sub(r'\bdb\.session\.commit\(\)', 'tenant_commit()', content)

    # Convert db.session.rollback() to tenant_rollback()
    content = re.sub(r'\bdb\.session\.rollback\(\)', 'tenant_rollback()', content)

    # Convert db.session.delete to tenant_delete
    content = re.sub(r'\bdb\.session\.delete\(', 'tenant_delete(', content)

    # Convert db.session.get to get_tenant_session().get
    content = re.sub(r'\bdb\.session\.get\(', 'get_tenant_session().get(', content)

    # Convert db.session.flush() to tenant_flush()
    content = re.sub(r'\bdb\.session\.flush\(\)', 'tenant_flush()', content)

    # Convert db.session.query to get_tenant_session().query
    content = re.sub(r'\bdb\.session\.query\(', 'get_tenant_session().query(', content)

    if content != original_content:
        modified = True

        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  [OK] Converted to multi-tenant")
        return True
    else:
        print(f"  [SKIP] No changes needed")
        return False


def main():
    """Convert all blueprint views to multi-tenant."""
    print("="*60)
    print("MULTI-TENANT CONVERSION SCRIPT")
    print("="*60)

    blueprints = [
        'inventory/views.py',
        'inventory/import_views.py',
        'checkout/views.py',
        'contacts/views.py',
        'properties/views.py',
        'smartlocks/views.py',
        'exports/views.py',
    ]

    converted = 0
    skipped = 0
    errors = 0

    for blueprint in blueprints:
        path = Path(blueprint)
        if not path.exists():
            print(f"[SKIP] {blueprint} - File not found")
            skipped += 1
            continue

        try:
            if convert_file_to_multitenant(path):
                converted += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"[ERROR] {blueprint}: {e}")
            errors += 1

    print("\n" + "="*60)
    print("CONVERSION SUMMARY")
    print("="*60)
    print(f"Converted: {converted}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")
    print("="*60)

    if converted > 0:
        print("\n[SUCCESS] Files converted! Restart the Flask server.")
    else:
        print("\n[INFO] No files needed conversion.")


if __name__ == "__main__":
    main()
