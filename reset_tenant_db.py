"""
Script to delete and recreate a tenant database with updated schema
"""
import os
import sys

# Tenant database to reset (change this to the one you're using)
TENANT_SUBDOMAIN = "vesta"  # or "demo"

tenant_db_path = f"C:/Users/dryan/WorkSpaces/KBM2.0/KBM2_data/tenants/{TENANT_SUBDOMAIN}.db"

if os.path.exists(tenant_db_path):
    print(f"Deleting old tenant database: {tenant_db_path}")
    os.remove(tenant_db_path)
    print("✓ Database deleted successfully!")
    print("\nThe database will be automatically recreated with the new schema")
    print(f"when you visit {TENANT_SUBDOMAIN}.localhost:5000 and log in.")
else:
    print(f"Database not found: {tenant_db_path}")
