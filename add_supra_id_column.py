#!/usr/bin/env python3
"""
Database migration script to add supra_id column to items table.

This script adds the optional supra_id field for Supra lockboxes to both:
1. Master database (if using multi-tenant setup)
2. All tenant databases

Run this after updating the code to add the supra_id field.

Usage:
    python add_supra_id_column.py
"""

import sqlite3
import os
import glob

def add_column_if_not_exists(db_path: str, table: str, column: str, column_type: str):
    """Add a column to a table if it doesn't already exist."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if column already exists
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]

        if column in columns:
            print(f"  ✓ Column '{column}' already exists in {table} - skipping")
            conn.close()
            return True

        # Add the column
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
        conn.commit()
        print(f"  ✓ Added column '{column}' to {table}")
        conn.close()
        return True

    except sqlite3.Error as e:
        print(f"  ✗ Error modifying {db_path}: {e}")
        return False

def main():
    print("=" * 60)
    print("Database Migration: Add supra_id column to items table")
    print("=" * 60)
    print()

    success_count = 0
    error_count = 0

    # Find all database files
    db_patterns = [
        "master_db/*.db",
        "tenant_dbs/*.db",
        "*.db"  # Fallback for non-dockerized setups
    ]

    databases = []
    for pattern in db_patterns:
        databases.extend(glob.glob(pattern))

    # Remove duplicates
    databases = list(set(databases))

    if not databases:
        print("No database files found!")
        print("Please ensure you're running this from the application root directory.")
        return

    print(f"Found {len(databases)} database(s) to migrate:")
    for db in databases:
        print(f"  - {db}")
    print()

    # Process each database
    for db_path in databases:
        print(f"Processing: {db_path}")

        # Check if items table exists
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'")
            has_items_table = cursor.fetchone() is not None
            conn.close()

            if not has_items_table:
                print(f"  ℹ Skipping - no 'items' table found")
                continue

        except sqlite3.Error as e:
            print(f"  ✗ Error checking {db_path}: {e}")
            error_count += 1
            continue

        # Add the column
        if add_column_if_not_exists(db_path, "items", "supra_id", "VARCHAR(50)"):
            success_count += 1
        else:
            error_count += 1
        print()

    # Summary
    print("=" * 60)
    print("Migration Summary:")
    print(f"  ✓ Successful: {success_count}")
    if error_count > 0:
        print(f"  ✗ Errors: {error_count}")
    print("=" * 60)
    print()

    if error_count == 0:
        print("✓ Migration completed successfully!")
        print("  You can now use the Supra ID field in lockbox forms.")
    else:
        print("⚠ Migration completed with errors.")
        print("  Please check the errors above and fix any issues.")

if __name__ == "__main__":
    main()
