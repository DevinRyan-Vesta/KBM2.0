#!/usr/bin/env python3
"""Add company name editing capability for accounts"""

# Step 1: Add route to app_admin/routes.py
routes_path = "app_admin/routes.py"
with open(routes_path, 'r', encoding='utf-8') as f:
    routes_content = f.read()

# Add the update company name route after the update_account_status route
new_route = '''

@app_admin_bp.route('/admin/accounts/<int:account_id>/update-name', methods=['POST'])
@login_required
@app_admin_required
@root_domain_only
def update_account_name(account_id):
    """
    Update account company name.
    """
    account = Account.query.get_or_404(account_id)
    new_name = request.form.get('company_name', '').strip()

    if not new_name:
        flash('Company name cannot be empty', 'error')
        return redirect(url_for('app_admin.view_account', account_id=account_id))

    old_name = account.company_name
    account.company_name = new_name

    master_db.session.commit()

    flash(f'Company name updated from "{old_name}" to "{new_name}"', 'success')
    return redirect(url_for('app_admin.view_account', account_id=account_id))
'''

# Find where to insert the new route (after update_account_status function)
marker = '''@app_admin_bp.route('/admin/accounts/<int:account_id>/delete', methods=['POST'])'''

if marker in routes_content and 'update_account_name' not in routes_content:
    routes_content = routes_content.replace(marker, new_route + '\n' + marker)
    with open(routes_path, 'w', encoding='utf-8') as f:
        f.write(routes_content)
    print(f"[OK] Added update_account_name route to {routes_path}")
else:
    if 'update_account_name' in routes_content:
        print(f"[OK] {routes_path} already has update_account_name route")
    else:
        print(f"[WARN] Could not find insertion point in {routes_path}")

# Step 2: Update account_detail.html template to add company name editing
template_path = "templates/app_admin/account_detail.html"
with open(template_path, 'r', encoding='utf-8') as f:
    template_content = f.read()

# Add company name editing section after the Account Information card
company_name_section = '''
<div class="card" style="margin-bottom: 24px;">
  <h2>Company Name</h2>
  <div class="divider"></div>
  <form method="POST" action="{{ url_for('app_admin.update_account_name', account_id=account.id) }}" class="toolbar">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
    <div class="form-field" style="max-width: 400px; flex: 1;">
      <label for="company_name">Company Name</label>
      <input type="text" id="company_name" name="company_name" value="{{ account.company_name }}" required>
    </div>
    <button type="submit" class="btn primary" style="margin-top: auto;">Update Name</button>
  </form>
</div>

'''

# Find where to insert (after the Account Information card, before Status Management)
marker2 = '<div class="card" style="margin-bottom: 24px;">\n  <h2>Status Management</h2>'

if marker2 in template_content and 'update_account_name' not in template_content:
    template_content = template_content.replace(marker2, company_name_section + marker2)
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(template_content)
    print(f"[OK] Added company name editing section to {template_path}")
else:
    if 'update_account_name' in template_content:
        print(f"[OK] {template_path} already has company name editing")
    else:
        print(f"[WARN] Could not find insertion point in {template_path}")

print("\n[OK] Company name editing functionality added!")
print("App admins can now edit company account names from the account detail page.")
