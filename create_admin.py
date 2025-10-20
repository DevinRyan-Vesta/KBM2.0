#!/usr/bin/env python3
"""Create a test admin account for the KBM application."""

from app import app
from utilities.database import db, User


def create_admin_account():
    """Create or update the admin test account."""
    with app.app_context():
        # Check if admin already exists
        existing = User.query.filter_by(role="admin").first()

        if existing:
            print(f"[OK] Admin account already exists: {existing.name} ({existing.email})")
            print(f"  User ID: {existing.id}")
            print(f"  Role: {existing.role}")
            return existing

        # Create new admin user
        admin = User(
            name="admin",
            email="devin@vestasells.com",
            role="admin"
        )
        admin.set_pin("1234")

        db.session.add(admin)
        db.session.commit()

        print("[OK] Admin account created successfully!")
        print(f"  Name: {admin.name}")
        print(f"  Email: {admin.email}")
        print(f"  Role: {admin.role}")
        print(f"  PIN: 1234")
        print(f"  User ID: {admin.id}")

        return admin


if __name__ == "__main__":
    create_admin_account()
