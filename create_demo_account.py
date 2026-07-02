#!/usr/bin/env python3
"""Provision a Demo tenant loaded with realistic sample data.

Creates (idempotently — safe to re-run, it recreates the demo tenant from
scratch each time):

  - Account  : subdomain "demo" (Demo Realty Group)
  - Users    : Demo Admin (PIN 1234), Demo Staff (PIN 5678)
  - Contacts : staff, contractors, tenants, agents
  - Properties with units
  - Lockboxes, keys (some low-stock), sign pieces + an assembled unit
  - Smart locks
  - Checkouts: active, overdue, upcoming, long-term, plus returned history
  - A completed audit

Usage:
    python create_demo_account.py

Then open http://demo.localhost:<PORT>/ and log in with PIN 1234.
"""
from datetime import timedelta

from app_multitenant import create_app
from utilities.master_database import master_db, Account, MasterUser
from utilities.tenant_manager import tenant_manager
from utilities.database import (
    db, Item, ItemCheckout, Contact, Property, PropertyUnit, SmartLock,
    Audit, AuditItem, utc_now,
)

SUBDOMAIN = "demo"
ADMIN_PIN = "1234"
STAFF_PIN = "5678"


def reset_demo_account(app):
    """Delete any existing demo tenant so the script is repeatable."""
    with app.app_context():
        master_db.create_all()
        existing = Account.query.filter_by(subdomain=SUBDOMAIN).first()
        if existing:
            print(f"Removing existing '{SUBDOMAIN}' tenant ...")
            MasterUser.query.filter_by(account_id=existing.id).delete()
            master_db.session.delete(existing)
            master_db.session.commit()
            tenant_manager.delete_tenant_database(existing)


def create_account(app):
    with app.app_context():
        account = Account(
            subdomain=SUBDOMAIN,
            company_name="Demo Realty Group",
            status="active",
            database_path=f"tenant_dbs/{SUBDOMAIN}.db",
        )
        master_db.session.add(account)
        master_db.session.commit()
        tenant_manager.create_tenant_database(account)

        admin = MasterUser(account_id=account.id, name="Demo Admin",
                           email="admin@demo.example", role="admin", is_active=True)
        admin.set_pin(ADMIN_PIN)
        staff = MasterUser(account_id=account.id, name="Demo Staff",
                           email="staff@demo.example", role="user", is_active=True)
        staff.set_pin(STAFF_PIN)
        master_db.session.add_all([admin, staff])
        master_db.session.commit()
        return account.id, admin.id, staff.id


def seed_tenant(app, admin_id):
    """Populate the demo tenant database directly via its engine."""
    from sqlalchemy.orm import Session

    engine = tenant_manager.get_tenant_engine(SUBDOMAIN)
    now = utc_now()

    with Session(engine) as s:
        # ---- Properties & units -------------------------------------
        maple = Property(name="Maple Court Apartments", type="multi_family",
                         address_line1="12 Maple St", city="Springfield",
                         state="IL", postal_code="62704",
                         notes="8-unit walk-up. Parking behind the building.")
        oak = Property(name="Oak Ridge House", type="single_family",
                       address_line1="450 Oak Ridge Dr", city="Springfield",
                       state="IL", postal_code="62711")
        pine = Property(name="Pine Plaza Offices", type="commercial",
                        address_line1="77 Pine Plaza", city="Springfield",
                        state="IL", postal_code="62701",
                        notes="Suite tenants; after-hours access via smart lock.")
        s.add_all([maple, oak, pine])
        s.flush()

        units = [PropertyUnit(property_id=maple.id, label=f"Unit {n}")
                 for n in ("1A", "1B", "2A", "2B")]
        units += [PropertyUnit(property_id=pine.id, label=f"Suite {n}")
                  for n in ("100", "200")]
        s.add_all(units)
        s.flush()

        # ---- Contacts ------------------------------------------------
        contacts = [
            Contact(name="Demo Staff", contact_type="staff", email="staff@demo.example",
                    phone="555-0101"),
            Contact(name="Carlos Martinez", contact_type="contractor",
                    company="Martinez Plumbing", email="carlos@example.test", phone="555-0102"),
            Contact(name="Priya Patel", contact_type="contractor",
                    company="Patel Painting", email="priya@example.test", phone="555-0103"),
            Contact(name="Alice Johnson", contact_type="tenant",
                    email="alice@example.test", phone="555-0104",
                    notes="Maple Court Unit 1A"),
            Contact(name="Sam Weaver", contact_type="tenant",
                    email="sam@example.test", phone="555-0105"),
            Contact(name="Dana Brooks", contact_type="agent",
                    company="Brooks Realty", email="dana@example.test", phone="555-0106"),
        ]
        s.add_all(contacts)
        s.flush()
        carlos, priya, alice, dana = contacts[1], contacts[2], contacts[3], contacts[5]

        # ---- Lockboxes -------------------------------------------------
        def lockbox(n, label, code, prev, prop, status="available", supra=None, assigned=None):
            return Item(type="Lockbox", custom_id=f"LBA{n:03d}", label=label,
                        status=status, code_current=code, code_previous=prev,
                        supra_id=supra, property_id=prop.id if prop else None,
                        address=(prop.address_line1 if prop else None),
                        location=None if prop else "Office storage",
                        assigned_to=assigned, last_action="created",
                        last_action_at=now, last_action_by_id=admin_id)

        lockboxes = [
            lockbox(1, "LB-Front Maple", "4417", "9282", maple, status="assigned",
                    assigned=maple.address_line1),
            lockbox(2, "LB-Oak Ridge", "8823", None, oak, status="assigned",
                    assigned=oak.address_line1, supra="SUP-33812"),
            lockbox(3, "LB-Spare 1", "1010", None, None),
            lockbox(4, "LB-Spare 2", "2020", "1515", None),
            lockbox(5, "LB-Pine Suite 200", "7345", "1988", pine, status="checked_out"),
        ]
        s.add_all(lockboxes)
        s.flush()

        # ---- Keys ------------------------------------------------------
        def key(n, label, hook, total, out, prop, unit=None, keycode=None, master=None):
            status = "checked_out" if out else "available"
            return Item(type="Key", custom_id=f"KA{n:03d}", label=label,
                        key_hook_number=hook, keycode=keycode,
                        total_copies=total, copies_checked_out=out, status=status,
                        property_id=prop.id if prop else None,
                        property_unit_id=unit.id if unit else None,
                        address=(prop.address_line1 if prop else None),
                        master_key_id=master.id if master else None,
                        last_action="created", last_action_at=now,
                        last_action_by_id=admin_id)

        master_key = key(1, "Maple Court Master", "H01", 3, 0, maple, keycode="M1001")
        s.add(master_key)
        s.flush()
        keys = [
            key(2, "Maple Unit 1A", "H02", 5, 1, maple, units[0], "K1102", master_key),
            key(3, "Maple Unit 1B", "H03", 4, 0, maple, units[1], "K1103", master_key),
            key(4, "Maple Unit 2A", "H04", 2, 1, maple, units[2], "K1104", master_key),  # low stock
            key(5, "Oak Ridge Front", "H05", 6, 2, oak, keycode="K2201"),
            key(6, "Oak Ridge Garage", "H06", 1, 0, oak),  # low stock
            key(7, "Pine Suite 100", "H07", 8, 0, pine, units[4]),
            key(8, "Pine Suite 200", "H08", 3, 1, pine, units[5]),
        ]
        s.add_all(keys)
        s.flush()

        # ---- Signs -----------------------------------------------------
        def sign(n, label, piece, status="available", material="Aluminum",
                 condition="Good", rider=None, parent=None, subtype="Piece"):
            return Item(type="Sign", custom_id=f"SA{n:03d}", label=label,
                        sign_subtype=subtype, piece_type=piece, rider_text=rider,
                        material=material, condition=condition, status=status,
                        parent_sign_id=parent, location="Sign rack",
                        last_action="created", last_action_at=now,
                        last_action_by_id=admin_id)

        assembled = sign(1, "Oak Ridge Yard Sign", None, status="assigned",
                         subtype="Assembled Unit")
        assembled.assigned_to = oak.address_line1
        assembled.property_id = oak.id
        assembled.location = None
        s.add(assembled)
        s.flush()
        signs = [
            sign(2, "Frame #1", "Frame", status="assigned", parent=assembled.id),
            sign(3, "For Rent Panel", "Sign", status="assigned", parent=assembled.id),
            sign(4, "Dana Brooks Rider", "Name Rider", status="assigned",
                 rider="Dana Brooks 555-0106", parent=assembled.id),
            sign(5, "Frame #2", "Frame"),
            sign(6, "For Sale Panel", "Sign", condition="Fair"),
            sign(7, "SOLD Rider", "Status Rider", rider="SOLD"),
            sign(8, "PENDING Rider", "Status Rider", rider="PENDING", condition="Excellent"),
        ]
        s.add_all(signs)
        s.flush()

        # ---- Smart locks -----------------------------------------------
        s.add_all([
            SmartLock(label="Pine Plaza Main Entry", code="24680#",
                      property_id=pine.id, notes="Code rotates quarterly."),
            SmartLock(label="Pine Suite 100 Door", code="13579#",
                      property_id=pine.id, property_unit_id=units[4].id),
        ])

        # ---- Checkouts (history + active/overdue/upcoming) -------------
        def co(item, to, contact, qty, purpose, out_days_ago, due_in_days=None,
               returned_days_ago=None):
            rec = ItemCheckout(
                item_id=item.id, checked_out_to=to,
                contact_id=contact.id if contact else None,
                checked_out_by_id=admin_id, quantity=qty, purpose=purpose,
                checked_out_at=now - timedelta(days=out_days_ago),
                expected_return_date=(now + timedelta(days=due_in_days)) if due_in_days is not None else None,
                is_active=returned_days_ago is None,
            )
            if returned_days_ago is not None:
                rec.checked_in_at = now - timedelta(days=returned_days_ago)
                rec.checked_in_by_id = admin_id
            return rec

        s.add_all([
            # Active — due next week
            co(keys[0], "Carlos Martinez", carlos, 1, "Unit 1A plumbing repair", 2, 7),
            # OVERDUE — was due 4 days ago
            co(keys[2], "Priya Patel", priya, 1, "Repaint Unit 2A", 12, -4),
            # Long-term (out 45 days), due in 15
            co(keys[3], "Sam Weaver", None, 2, "Landscaping access", 45, 15),
            # Active lockbox checkout — due tomorrow
            co(lockboxes[4], "Dana Brooks", dana, 1, "Suite 200 showings", 1, 1),
            # Upcoming — key out, due in 3 days
            co(keys[7], "Dana Brooks", dana, 1, "Tenant walkthrough", 3, 3),
            # Returned history
            co(keys[4], "Alice Johnson", alice, 1, "Move-in", 30, None, returned_days_ago=25),
            co(keys[1], "Carlos Martinez", carlos, 1, "Radiator fix", 20, None, returned_days_ago=18),
        ])

        # ---- A completed audit -----------------------------------------
        audit = Audit(created_by_user_id=admin_id, status="completed",
                      created_at=now - timedelta(days=14),
                      completed_at=now - timedelta(days=14))
        s.add(audit)
        s.flush()
        for k in [master_key] + keys:
            s.add(AuditItem(
                audit_id=audit.id, item_id=k.id,
                expected_location=k.key_hook_number,
                expected_quantity=k.total_copies or 0,
                actual_location=k.key_hook_number,
                actual_quantity=k.total_copies or 0,
                discrepancy_type="none",
                audited_at=now - timedelta(days=14),
            ))

        s.commit()

    print("Demo tenant data created.")


def main():
    app = create_app()
    reset_demo_account(app)
    account_id, admin_id, staff_id = create_account(app)
    seed_tenant(app, admin_id)

    print()
    print("=" * 56)
    print("Demo account ready!")
    print(f"  Company   : Demo Realty Group  (subdomain: {SUBDOMAIN})")
    print(f"  Admin PIN : {ADMIN_PIN}   (Demo Admin)")
    print(f"  Staff PIN : {STAFF_PIN}   (Demo Staff)")
    print()
    print("Open http://demo.localhost:<PORT>/ (or demo.<your-domain>)")
    print("and log in with one of the PINs above.")
    print("=" * 56)


if __name__ == "__main__":
    main()
