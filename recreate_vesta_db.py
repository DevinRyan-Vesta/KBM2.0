#!/usr/bin/env python3
"""
Recreate the vesta tenant database.
"""

from app_multitenant import app
from utilities.master_database import master_db, Account
from utilities.tenant_manager import tenant_manager
import os

def recreate_vesta_db():
    """Recreate the vesta tenant database."""
    print("Recreating vesta tenant database...")

    with app.app_context():
        # Get the vesta account
        account = Account.query.filter_by(subdomain='vesta').first()

        if not account:
            print("ERROR: Vesta account not found in master database!")
            print("Available accounts:")
            for acc in Account.query.all():
                print(f"  - {acc.subdomain} ({acc.company_name})")
            return False

        # Get the database path
        db_path = tenant_manager.get_tenant_database_path(account)

        # Delete old database if it exists
        if db_path.exists():
            print(f"Deleting old database: {db_path}")
            os.remove(db_path)

        # Create new database
        print(f"Creating new database: {db_path}")
        tenant_manager.create_tenant_database(account)

        print("✓ Vesta tenant database recreated successfully!")
        return True

if __name__ == "__main__":
    if recreate_vesta_db():
        print("\nYou can now access vesta.localhost:5000")
    else:
        print("\nFailed to recreate database")
