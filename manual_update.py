#!/usr/bin/env python3
"""
Manual update script to pull latest changes and restart containers.
This bypasses the web UI and runs the update directly.
"""
import sys
sys.path.insert(0, r'C:\Users\dryan\WorkSpaces\KBM2.0')

from utilities.system_update import update_manager

print("=" * 60)
print("MANUAL SYSTEM UPDATE")
print("=" * 60)

# Step 1: Check current version
print("\n[1/4] Current Version:")
current = update_manager.get_current_version()
print(f"  Commit: {current.get('commit_hash')} - {current.get('commit_message')}")
print(f"  Branch: {current.get('branch')}")
print(f"  Date: {current.get('commit_date')}")

# Step 2: Check for updates
print("\n[2/4] Checking for updates...")
update_check = update_manager.check_for_updates()
if 'error' in update_check:
    print(f"  ERROR: {update_check['error']}")
    sys.exit(1)

if update_check.get('has_updates'):
    print(f"  Found {update_check['update_count']} update(s):")
    for update in update_check.get('updates', []):
        print(f"    - {update['commit_hash']} {update['message']}")
else:
    print("  No updates available")
    sys.exit(0)

# Step 3: Pull updates
print("\n[3/4] Pulling updates...")
success, output = update_manager.pull_updates()
if success:
    print(f"  SUCCESS: {output}")
else:
    print(f"  FAILED: {output}")
    sys.exit(1)

# Step 4: Restart containers
print("\n[4/4] Restarting containers...")
success, message = update_manager.restart_containers()
if success:
    print(f"  SUCCESS: {message}")
else:
    print(f"  FAILED: {message}")
    sys.exit(1)

print("\n" + "=" * 60)
print("UPDATE COMPLETED SUCCESSFULLY!")
print("=" * 60)
print("\nThe application has been updated and restarted.")
print("Template changes are now active (no rebuild needed).")
