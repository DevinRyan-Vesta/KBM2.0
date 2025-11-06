#!/usr/bin/env python3
"""
Database migration script to add audit tables (audits and audit_items).
Run this script to add the new tables to all tenant databases.
"""
import sqlite3
import glob
from pathlib import Path

def add_audit_tables(db_path):
    """Add audits and audit_items tables to a database if they don't exist"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if audits table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='audits'
        """)
        audits_exists = cursor.fetchone() is not None

        if not audits_exists:
            # Create audits table
            cursor.execute("""
                CREATE TABLE audits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at DATETIME NOT NULL,
                    audit_date DATETIME NOT NULL,
                    created_by_user_id INTEGER NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    notes TEXT,
                    completed_at DATETIME
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX ix_audits_created_by_user_id ON audits(created_by_user_id)
            """)

            conn.commit()
            print(f"  ✓ Created audits table")
        else:
            print(f"  - audits table already exists")

        # Check if audit_items table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='audit_items'
        """)
        audit_items_exists = cursor.fetchone() is not None

        if not audit_items_exists:
            # Create audit_items table
            cursor.execute("""
                CREATE TABLE audit_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    audit_id INTEGER NOT NULL,
                    item_id INTEGER NOT NULL,
                    expected_location VARCHAR(120),
                    expected_quantity INTEGER,
                    actual_location VARCHAR(120),
                    actual_quantity INTEGER,
                    discrepancy_type VARCHAR(50),
                    notes TEXT,
                    audited_at DATETIME,
                    FOREIGN KEY (audit_id) REFERENCES audits(id) ON DELETE CASCADE,
                    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX ix_audit_items_audit_id ON audit_items(audit_id)
            """)
            cursor.execute("""
                CREATE INDEX ix_audit_items_item_id ON audit_items(item_id)
            """)

            conn.commit()
            print(f"  ✓ Created audit_items table")
        else:
            print(f"  - audit_items table already exists")

        return True

    except Exception as e:
        print(f"  ✗ Error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def main():
    """Main migration function"""
    print("=" * 60)
    print("Audit Tables Migration Script")
    print("=" * 60)
    print()

    # Find all database files
    db_patterns = [
        "master_db/*.db",
        "tenant_dbs/*.db",
        "*.db"
    ]

    all_dbs = set()
    for pattern in db_patterns:
        all_dbs.update(glob.glob(pattern))

    if not all_dbs:
        print("No database files found.")
        return

    print(f"Found {len(all_dbs)} database file(s):\n")

    success_count = 0
    for db_path in sorted(all_dbs):
        print(f"Processing: {db_path}")
        if add_audit_tables(db_path):
            success_count += 1
        print()

    print("=" * 60)
    print(f"Migration complete: {success_count}/{len(all_dbs)} databases updated")
    print("=" * 60)


if __name__ == "__main__":
    main()
