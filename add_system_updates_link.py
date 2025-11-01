#!/usr/bin/env python3
"""Add System Updates link to app admin dashboard"""

dashboard_path = "templates/app_admin/dashboard.html"
with open(dashboard_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Check if system updates link already exists
if 'system_updates' not in content:
    # Find the Quick Actions section and add the link
    old_quick_actions = '''            <a href="{{ url_for('app_admin.list_app_admins') }}" class="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700">
                Manage Admins
            </a>
        </div>'''

    new_quick_actions = '''            <a href="{{ url_for('app_admin.list_app_admins') }}" class="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700">
                Manage Admins
            </a>
            <a href="{{ url_for('app_admin.system_updates') }}" class="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700">
                System Updates
            </a>
        </div>'''

    if old_quick_actions in content:
        content = content.replace(old_quick_actions, new_quick_actions)
        with open(dashboard_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[OK] Added System Updates link to {dashboard_path}")
    else:
        print(f"[WARN] Could not find Quick Actions section in {dashboard_path}")
else:
    print(f"[OK] {dashboard_path} already has System Updates link")

print("\n[OK] Dashboard updated!")
