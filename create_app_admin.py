#!/usr/bin/env python3
"""
Create an App Admin account for KBM 2.0 Multi-Tenant Application.

App Admins have access to the admin panel at the root domain to manage
all tenant accounts.
"""

import sys
import getpass
from app_multitenant import create_app
from utilities.master_database import master_db, MasterUser


def validate_pin(pin: str) -> bool:
    """Validate PIN is exactly 4 digits."""
    return pin.isdigit() and len(pin) == 4


def validate_email(email: str) -> bool:
    """Basic email validation."""
    return '@' in email and '.' in email.split('@')[1]


def create_app_admin():
    """Create an App Admin account interactively."""
    app = create_app()

    with app.app_context():
        print("=" * 60)
        print("KBM 2.0 - Create App Admin Account")
        print("=" * 60)
        print()
        print("App Admins can:")
        print("  - Access the admin panel at the root domain")
        print("  - Manage all tenant accounts")
        print("  - View system-wide statistics")
        print()

        # Get name
        while True:
            name = input("Enter admin name: ").strip()
            if name:
                break
            print("❌ Name cannot be empty!")

        # Get email
        while True:
            email = input("Enter admin email: ").strip().lower()
            if validate_email(email):
                # Check if email already exists as app_admin
                existing = master_db.session.query(MasterUser).filter_by(
                    email=email,
                    role='app_admin'
                ).first()
                if existing:
                    print(f"❌ An app admin with email '{email}' already exists!")
                    print(f"   Name: {existing.name}")
                    print(f"   Created: {existing.created_at}")
                    print()
                    continue_anyway = input("Do you want to enter a different email? (y/n): ").strip().lower()
                    if continue_anyway == 'y':
                        continue
                    else:
                        print("Exiting...")
                        return
                break
            print("❌ Invalid email format!")

        # Get secure PIN
        print()
        print("PIN Requirements:")
        print("  - Must be exactly 4 digits")
        print("  - Avoid simple patterns (1234, 0000, 1111, etc.)")
        print("  - Use a memorable but secure combination")
        print()

        while True:
            pin = getpass.getpass("Enter 4-digit PIN (hidden): ").strip()

            if not validate_pin(pin):
                print("❌ PIN must be exactly 4 digits!")
                continue

            # Check for weak PINs
            weak_pins = ['1234', '0000', '1111', '2222', '3333', '4444',
                        '5555', '6666', '7777', '8888', '9999', '0123',
                        '4321', '1212', '6969']

            if pin in weak_pins:
                print(f"⚠️  WARNING: '{pin}' is a common/weak PIN!")
                use_anyway = input("Use it anyway? (not recommended) (y/n): ").strip().lower()
                if use_anyway != 'y':
                    continue

            # Confirm PIN
            pin_confirm = getpass.getpass("Confirm PIN (hidden): ").strip()

            if pin != pin_confirm:
                print("❌ PINs do not match! Try again.")
                continue

            break

        # Create admin
        print()
        print("Creating App Admin account...")

        admin = MasterUser(
            name=name,
            email=email,
            role='app_admin',
            account_id=None  # App admins have no associated tenant account
        )
        admin.set_pin(pin)

        master_db.session.add(admin)
        master_db.session.commit()

        print()
        print("=" * 60)
        print("✅ App Admin Account Created Successfully!")
        print("=" * 60)
        print(f"Name:  {admin.name}")
        print(f"Email: {admin.email}")
        print(f"PIN:   {'*' * len(pin)} (hidden)")
        print(f"ID:    {admin.id}")
        print()
        print("Access the admin panel at:")
        print("  https://yourdomain.com/app-admin")
        print()
        print("Login with:")
        print(f"  Email: {admin.email}")
        print(f"  PIN:   (the PIN you just created)")
        print()


if __name__ == "__main__":
    try:
        create_app_admin()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error creating admin account: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
