#!/usr/bin/env python3
"""Update ToDo.txt to mark system updates UI as completed"""

with open('ToDo.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and update the system updates line
for i, line in enumerate(lines):
    if 'Can we create a UI by which i can update the app' in line:
        # Move to completed section
        break

# Read the whole file
with open('ToDo.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the line
content = content.replace(
    '[ ] Can we create a UI by which i can update the app, typing in a whole bunch of command lines isn\'t my thing.',
    ''
)

# Add to completed section
content = content.replace(
    '[✓] The company accounts need to be able to have their name edited - FIXED',
    '[✓] The company accounts need to be able to have their name edited - FIXED\n[✓] Can we create a UI by which i can update the app, typing in a whole bunch of command lines isn\'t my thing - FIXED'
)

# Add reference information at the end
if 'SYSTEM UPDATE UI' not in content:
    additional_info = '''
7. SYSTEM UPDATE UI
   Files Created:
   - utilities/system_update.py: Core update management functionality
   - app_admin/routes.py: Added system update routes
   - templates/app_admin/system_updates.html: Web UI for updates
   - SYSTEM_UPDATES_GUIDE.md: Complete user guide

   What was added:
   - Check for GitHub updates with one click
   - One-click system update (with or without Docker rebuild)
   - Container status monitoring
   - Real-time log viewing
   - Automatic database backups before updates
   - Restart containers without updating
   - Download logs functionality

   Access:
   - Login as app admin
   - Navigate to root domain
   - Click "System Updates" in Quick Actions
'''

    # Find where to insert (before TESTING RECOMMENDATIONS)
    content = content.replace(
        'Scripts Created (can be re-run if needed):',
        'Scripts Created (can be re-run if needed):\n- add_update_ui_routes.py\n- add_system_updates_link.py\n- update_todo_system_updates.py' + additional_info + '\n\nScripts Created (can be re-run if needed):'
    )

    # Fix the duplicate
    content = content.replace('Scripts Created (can be re-run if needed):\nScripts Created (can be re-run if needed):', 'Scripts Created (can be re-run if needed):')

with open('ToDo.txt', 'w', encoding='utf-8') as f:
    f.write(content)

print("[OK] ToDo.txt updated with System Updates UI completion")
print("\n" + "="*60)
print("SYSTEM UPDATES UI COMPLETE!")
print("="*60)
print("\nFeatures:")
print("  - Check for updates from GitHub")
print("  - One-click updates (with or without rebuild)")
print("  - Container management and monitoring")
print("  - Real-time log viewing")
print("  - Automatic database backups")
print("\nHow to access:")
print("  1. Login as app admin")
print("  2. Go to root domain (http://yourdomain:8080)")
print("  3. Click 'System Updates' in Quick Actions")
print("\nSee SYSTEM_UPDATES_GUIDE.md for full documentation")
