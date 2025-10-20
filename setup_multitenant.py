#!/usr/bin/env python3
"""
Multi-tenant setup script for KBM application.

This script:
1. Creates the master database
2. Creates the first app admin user
3. Optionally creates a demo tenant account
"""

import sys
from app_multitenant import app
from utilities.master_database import master_db, Account, MasterUser
from utilities.tenant_manager import tenant_manager
import re


def create_master_database():
    """Create master database schema."""
    print("[1/4] Creating master database...")

    with app.app_context():
        master_db.create_all()
        print("  [OK] Master database created")


def create_app_admin():
    """Create first app admin user."""
    print("\n[2/4] Creating app admin user...")

    with app.app_context():
        # Check if app admin already exists
        existing = MasterUser.query.filter_by(role='app_admin').first()
        if existing:
            print(f"  [SKIP] App admin already exists: {existing.name} ({existing.email})")
            return existing

        print("\n  Enter details for the first app admin:")
        name = input("    Name: ").strip()
        email = input("    Email: ").strip()

        while True:
            pin = input("    PIN (4+ characters): ").strip()
            if len(pin) >= 4:
                break
            print("    PIN must be at least 4 characters")

        admin = MasterUser(
            account_id=None,
            name=name,
            email=email,
            role='app_admin',
            is_active=True
        )
        admin.set_pin(pin)

        master_db.session.add(admin)
        master_db.session.commit()

        print(f"  [OK] App admin created: {name} ({email})")
        return admin


def create_demo_account():
    """Optionally create a demo tenant account."""
    print("\n[3/4] Demo tenant account")

    with app.app_context():
        create_demo = input("  Create a demo tenant account? (y/N): ").strip().lower()
        if create_demo != 'y':
            print("  [SKIP] Skipping demo account")
            return None

        print("\n  Enter details for the demo account:")

        while True:
            subdomain = input("    Subdomain (e.g., 'demo'): ").strip().lower()
            is_valid, error_msg = Account.validate_subdomain(subdomain)
            if is_valid:
                break
            print(f"    Error: {error_msg}")

        company_name = input("    Company name: ").strip()
        admin_name = input("    Admin name: ").strip()
        admin_email = input("    Admin email: ").strip()

        while True:
            admin_pin = input("    Admin PIN (4+ characters): ").strip()
            if len(admin_pin) >= 4:
                break
            print("    PIN must be at least 4 characters")

        # Create account
        account = Account(
            subdomain=subdomain,
            company_name=company_name,
            status='active'
        )

        db_path = tenant_manager.get_tenant_database_path(account)
        account.database_path = str(db_path)

        master_db.session.add(account)
        master_db.session.flush()

        # Create tenant database
        print(f"    Creating database for {subdomain}...")
        tenant_manager.create_tenant_database(account)

        # Create admin user
        admin_user = MasterUser(
            account_id=account.id,
            name=admin_name,
            email=admin_email,
            role='admin'
        )
        admin_user.set_pin(admin_pin)

        master_db.session.add(admin_user)
        master_db.session.commit()

        print(f"  [OK] Demo account created: {company_name}")
        print(f"      URL: http://{subdomain}.localhost:5000")
        print(f"      Admin: {admin_name} (PIN: {admin_pin})")

        return account


def print_summary():
    """Print setup summary and next steps."""
    print("\n[4/4] Setup complete!")
    print("\n" + "="*60)
    print("MULTI-TENANT SETUP SUMMARY")
    print("="*60)

    with app.app_context():
        app_admins = MasterUser.query.filter_by(role='app_admin').all()
        accounts = Account.query.all()

        print(f"\nApp Admins: {len(app_admins)}")
        for admin in app_admins:
            print(f"  - {admin.name} ({admin.email})")

        print(f"\nTenant Accounts: {len(accounts)}")
        for account in accounts:
            user_count = len(account.users)
            print(f"  - {account.company_name} ({account.subdomain}) - {user_count} user(s)")

    print("\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("\n1. Start the application:")
    print("   python app_multitenant.py")
    print("\n2. Access the app:")
    print("   - Root domain:     http://localhost:5000")
    print("   - App admin login: http://localhost:5000/auth/login")
    print("   - Tenant domain:   http://SUBDOMAIN.localhost:5000")
    print("\n3. Create accounts:")
    print("   - Go to http://localhost:5000/accounts/signup")
    print("   - Or use the app admin dashboard to manage accounts")
    print("\n4. For production:")
    print("   - Set SERVER_NAME in config (e.g., 'yourdomain.com')")
    print("   - Configure DNS wildcards (*.yourdomain.com)")
    print("   - Use a production WSGI server (gunicorn, etc.)")
    print("\n" + "="*60)


def main():
    """Main setup function."""
    print("="*60)
    print("KBM MULTI-TENANT SETUP")
    print("="*60)

    try:
        create_master_database()
        create_app_admin()
        create_demo_account()
        print_summary()

        print("\n[SUCCESS] Setup completed successfully!")
        return 0

    except KeyboardInterrupt:
        print("\n\n[CANCELLED] Setup cancelled by user")
        return 1

    except Exception as e:
        print(f"\n[ERROR] Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
