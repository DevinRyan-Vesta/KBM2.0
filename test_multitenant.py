#!/usr/bin/env python3
"""
Automated test script for multi-tenant setup.
"""

from app_multitenant import app
from utilities.master_database import master_db, Account, MasterUser
from utilities.tenant_manager import tenant_manager


def setup_test_data():
    """Create test data for multi-tenant system."""
    print("Creating test data...")

    with app.app_context():
        # Create master database
        print("1. Creating master database schema...")
        master_db.create_all()
        print("   [OK] Master database created")

        # Create app admin
        print("\n2. Creating app admin...")
        existing_admin = MasterUser.query.filter_by(role='app_admin', email='admin@test.com').first()
        if existing_admin:
            print(f"   [EXISTS] App admin already exists: {existing_admin.name}")
            app_admin = existing_admin
        else:
            app_admin = MasterUser(
                account_id=None,
                name='App Admin',
                email='admin@test.com',
                role='app_admin',
                is_active=True
            )
            app_admin.set_pin('1234')
            master_db.session.add(app_admin)
            master_db.session.commit()
            print(f"   [OK] App admin created: {app_admin.name} (PIN: 1234)")

        # Create test tenant account
        print("\n3. Creating test tenant account...")
        existing_account = Account.query.filter_by(subdomain='demo').first()
        if existing_account:
            print(f"   [EXISTS] Account already exists: {existing_account.company_name}")
            account = existing_account
        else:
            account = Account(
                subdomain='demo',
                company_name='Demo Company',
                status='active'
            )
            db_path = tenant_manager.get_tenant_database_path(account)
            account.database_path = str(db_path)

            master_db.session.add(account)
            master_db.session.flush()

            print("   Creating tenant database...")
            tenant_manager.create_tenant_database(account)
            print(f"   [OK] Tenant database created at: {db_path}")

            # Create tenant admin user
            tenant_admin = MasterUser(
                account_id=account.id,
                name='Demo Admin',
                email='admin@demo.com',
                role='admin',
                is_active=True
            )
            tenant_admin.set_pin('5678')
            master_db.session.add(tenant_admin)
            master_db.session.commit()

            print(f"   [OK] Tenant admin created: {tenant_admin.name} (PIN: 5678)")

        print("\n" + "="*60)
        print("TEST DATA SUMMARY")
        print("="*60)
        print("\nApp Admin:")
        print("  URL:   http://localhost:5000/auth/login")
        print("  Email: admin@test.com")
        print("  PIN:   1234")
        print("\nDemo Tenant:")
        print("  URL:   http://demo.localhost:5000")
        print("  Email: admin@demo.com")
        print("  PIN:   5678")
        print("\n" + "="*60)
        print("\nNext: Start the app with 'python app_multitenant.py'")
        print("="*60)


if __name__ == "__main__":
    try:
        setup_test_data()
        print("\n[SUCCESS] Test data created successfully!")
    except Exception as e:
        print(f"\n[ERROR] Failed to create test data: {e}")
        import traceback
        traceback.print_exc()
