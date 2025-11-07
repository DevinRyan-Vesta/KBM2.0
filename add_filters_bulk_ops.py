#!/usr/bin/env python3
"""
Script to add advanced filtering and bulk operations to lockboxes and signs templates.
This applies the same pattern used in keys.html to ensure consistency.
"""

def add_filters_and_bulk_to_lockboxes():
    """Add filters and bulk operations to lockboxes.html"""
    file_path = 'templates/lockboxes.html'

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Add Filters button to toolbar
    content = content.replace(
        '<a class="btn small" href="{{ url_for(\'inventory.import_lockboxes\') }}">Import</a>',
        '''<button type="button" class="btn small" onclick="toggleFilters()">Filters ▾</button>
      <button type="button" class="btn small" onclick="showExportMenu(event, 'lockboxes')">Export ▾</button>
      <a class="btn small" href="{{ url_for('inventory.import_lockboxes') }}">Import</a>'''
    )

    # 2. Add filter section (find where to insert - after page header, before export menu)
    filter_html = '''
<!-- Advanced Filters -->
<div id="advanced-filters" class="card" style="display: {% if filter_status or filter_property or filter_assigned %}block{% else %}none{% endif %}; margin-bottom: 20px;">
  <form method="get" action="{{ url_for('inventory.list_lockboxes') }}" style="display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end;">
    <input type="hidden" name="q" value="{{ q or '' }}">

    <div class="form-field" style="margin: 0; flex: 1; min-width: 180px;">
      <label for="filter-status" style="font-size: 13px; margin-bottom: 4px;">Status</label>
      <select name="status" id="filter-status" style="width: 100%;">
        <option value="">All Statuses</option>
        {% for status in status_options %}
        <option value="{{ status }}" {% if filter_status and filter_status.lower() == status.lower() %}selected{% endif %}>
          {{ status.replace('_', ' ').title() }}
        </option>
        {% endfor %}
      </select>
    </div>

    <div class="form-field" style="margin: 0; flex: 1; min-width: 200px;">
      <label for="filter-property" style="font-size: 13px; margin-bottom: 4px;">Property</label>
      <select name="property" id="filter-property" style="width: 100%;">
        {% for prop in property_select_options %}
        <option value="{{ prop[0] }}" {% if filter_property and filter_property == prop[0] %}selected{% endif %}>
          {{ prop[1] }}
        </option>
        {% endfor %}
      </select>
    </div>

    <div class="form-field" style="margin: 0; flex: 1; min-width: 160px;">
      <label for="filter-assigned" style="font-size: 13px; margin-bottom: 4px;">Assignment</label>
      <select name="assigned" id="filter-assigned" style="width: 100%;">
        <option value="">All Items</option>
        <option value="assigned" {% if filter_assigned == 'assigned' %}selected{% endif %}>Assigned</option>
        <option value="unassigned" {% if filter_assigned == 'unassigned' %}selected{% endif %}>Unassigned</option>
      </select>
    </div>

    <div style="display: flex; gap: 8px;">
      <button type="submit" class="btn small primary">Apply Filters</button>
      {% if filter_status or filter_property or filter_assigned %}
      <a href="{{ url_for('inventory.list_lockboxes', q=q or '') }}" class="btn small ghost">Clear Filters</a>
      {% endif %}
    </div>
  </form>
</div>

'''

    # Insert filter section before the export menu
    content = content.replace(
        '<div id="export-menu"',
        filter_html + '<div id="export-menu"'
    )

    # 3. Add bulk operations toolbar
    bulk_toolbar_html = '''<!-- Bulk Actions Toolbar -->
<div class="bulkbar" id="bulk-toolbar">
  <input type="checkbox" id="select-all-checkbox" onclick="toggleSelectAll(this)" style="margin: 0;">
  <span id="bulk-count">0 selected</span>
  <select id="bulk-action" class="form-control" style="max-width: 200px;">
    <option value="">-- Select Action --</option>
    <option value="delete">Delete Selected</option>
    <option value="change-status">Change Status</option>
    <option value="assign">Assign To...</option>
  </select>
  <button type="button" class="btn small primary" onclick="executeBulkAction()">Execute</button>
  <button type="button" class="btn small ghost" onclick="clearSelection()">Cancel</button>
</div>

'''

    # Insert bulk toolbar before the table card
    content = content.replace(
        '<div class="card table-card">',
        bulk_toolbar_html + '<div class="card table-card">'
    )

    # 4. Add checkbox column to table header
    content = content.replace(
        '''<thead>
        <tr>
          <th>Label</th>''',
        '''<thead>
        <tr>
          <th class="select-col"><input type="checkbox" id="th-select-all" onclick="toggleSelectAll(this)" style="margin: 0;"></th>
          <th>Label</th>'''
    )

    # 5. Add checkbox and data attributes to table rows
    content = content.replace(
        '''{% for lockbox in lockboxes %}
          {% set status_lower = (lockbox.status or '')|lower %}
          <tr>''',
        '''{% for lockbox in lockboxes %}
          {% set status_lower = (lockbox.status or '')|lower %}
          <tr data-item-id="{{ lockbox.id }}" data-item-label="{{ lockbox.label }}">
            <td class="select-col">
              <input type="checkbox" class="item-checkbox" value="{{ lockbox.id }}" onchange="updateBulkToolbar()" style="margin: 0;">
            </td>'''
    )

    # 6. Add CSS for bulk operations (add after existing style block if exists, or create new one)
    bulk_css = '''
  .bulkbar {
    display: none;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border-radius: 12px;
    border: 1px solid var(--color-border);
    background: rgba(229, 57, 53, 0.08);
    color: var(--color-text);
    margin-bottom: 18px;
  }
  .bulkbar.show { display: flex; }
  .select-col { width: 40px; }
'''

    # Find the style section and add bulk CSS
    if '<style>' in content:
        content = content.replace('<style>', '<style>' + bulk_css)
    else:
        # Add style section before content block
        content = content.replace('{% block content %}', '''{% block content %}
<style>''' + bulk_css + '''
</style>
''')

    # 7. Add JavaScript functions before closing </script> or at end
    js_code = '''

  // === Filter and Bulk Operations ===

  function toggleFilters() {
    const filtersDiv = document.getElementById('advanced-filters');
    if (filtersDiv.style.display === 'none' || filtersDiv.style.display === '') {
      filtersDiv.style.display = 'block';
    } else {
      filtersDiv.style.display = 'none';
    }
  }

  function getSelectedItems() {
    const checkboxes = document.querySelectorAll('.item-checkbox:checked');
    return Array.from(checkboxes).map(cb => cb.value);
  }

  function updateBulkToolbar() {
    const selectedIds = getSelectedItems();
    const toolbar = document.getElementById('bulk-toolbar');
    const countSpan = document.getElementById('bulk-count');
    const selectAllCheckbox = document.getElementById('select-all-checkbox');
    const thSelectAll = document.getElementById('th-select-all');

    if (selectedIds.length > 0) {
      toolbar.classList.add('show');
      countSpan.textContent = `${selectedIds.length} selected`;
    } else {
      toolbar.classList.remove('show');
      countSpan.textContent = '0 selected';
    }

    const allCheckboxes = document.querySelectorAll('.item-checkbox');
    const allChecked = allCheckboxes.length > 0 && selectedIds.length === allCheckboxes.length;
    if (selectAllCheckbox) selectAllCheckbox.checked = allChecked;
    if (thSelectAll) thSelectAll.checked = allChecked;
  }

  function toggleSelectAll(checkbox) {
    const checkboxes = document.querySelectorAll('.item-checkbox');
    checkboxes.forEach(cb => {
      cb.checked = checkbox.checked;
    });
    updateBulkToolbar();
  }

  function clearSelection() {
    const checkboxes = document.querySelectorAll('.item-checkbox');
    checkboxes.forEach(cb => {
      cb.checked = false;
    });
    updateBulkToolbar();
  }

  function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  async function executeBulkAction() {
    const selectedIds = getSelectedItems();
    if (selectedIds.length === 0) {
      alert('Please select at least one item.');
      return;
    }

    const action = document.getElementById('bulk-action').value;
    if (!action) {
      alert('Please select an action.');
      return;
    }

    if (action === 'delete') {
      if (!confirm(`Are you sure you want to delete ${selectedIds.length} item(s)? This cannot be undone.`)) {
        return;
      }
      await bulkDelete(selectedIds);
    } else if (action === 'change-status') {
      const newStatus = prompt('Enter new status (available, assigned, checked_out, maintenance, retired):');
      if (newStatus) {
        await bulkUpdateStatus(selectedIds, newStatus);
      }
    } else if (action === 'assign') {
      const assignTo = prompt('Enter person to assign to (leave blank to unassign):');
      if (assignTo !== null) {
        await bulkAssign(selectedIds, assignTo);
      }
    }
  }

  async function bulkDelete(itemIds) {
    try {
      const response = await fetch('/inventory/bulk/delete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': getCsrfToken()
        },
        body: new URLSearchParams({
          item_ids: itemIds.join(','),
          item_type: 'lockbox'
        })
      });

      const data = await response.json();
      if (data.success) {
        alert(data.message);
        window.location.reload();
      } else {
        alert('Error: ' + data.error);
      }
    } catch (error) {
      alert('Error performing bulk delete: ' + error);
    }
  }

  async function bulkUpdateStatus(itemIds, newStatus) {
    try {
      const response = await fetch('/inventory/bulk/update_status', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': getCsrfToken()
        },
        body: new URLSearchParams({
          item_ids: itemIds.join(','),
          status: newStatus
        })
      });

      const data = await response.json();
      if (data.success) {
        alert(data.message);
        window.location.reload();
      } else {
        alert('Error: ' + data.error);
      }
    } catch (error) {
      alert('Error performing bulk status update: ' + error);
    }
  }

  async function bulkAssign(itemIds, assignTo) {
    try {
      const response = await fetch('/inventory/bulk/assign', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': getCsrfToken()
        },
        body: new URLSearchParams({
          item_ids: itemIds.join(','),
          assigned_to: assignTo
        })
      });

      const data = await response.json();
      if (data.success) {
        alert(data.message);
        window.location.reload();
      } else {
        alert('Error: ' + data.error);
      }
    } catch (error) {
      alert('Error performing bulk assign: ' + error);
    }
  }
'''

    # Add JS before </script> if exists, otherwise before {% endblock %}
    if '</script>' in content:
        content = content.replace('</script>', js_code + '\n</script>')
    else:
        content = content.replace('{% endblock %}', '<script>' + js_code + '\n</script>\n{% endblock %}')

    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"[OK] Updated {file_path}")


def add_filters_and_bulk_to_signs():
    """Add filters and bulk operations to signs.html - similar to lockboxes"""
    file_path = 'templates/signs.html'

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # The signs template already has some changes - just need to add filters button and sections

    # 1. Add Filters button to toolbar (find the import button first)
    if 'onclick="toggleFilters()">Filters' not in content:
        content = content.replace(
            '<a class="btn small" href="{{ url_for(\'inventory.import_signs\') }}">Import</a>',
            '''<button type="button" class="btn small" onclick="toggleFilters()">Filters ▾</button>
      <a class="btn small" href="{{ url_for('inventory.import_signs') }}">Import</a>'''
        )

    # 2. Add filter section
    filter_html = '''
<!-- Advanced Filters -->
<div id="advanced-filters" class="card" style="display: {% if filter_status or filter_property or filter_assigned %}block{% else %}none{% endif %}; margin-bottom: 20px;">
  <form method="get" action="{{ url_for('inventory.list_signs') }}" style="display: flex; gap: 12px; flex-wrap: wrap; align-items: flex-end;">
    <input type="hidden" name="q" value="{{ q or '' }}">

    <div class="form-field" style="margin: 0; flex: 1; min-width: 180px;">
      <label for="filter-status" style="font-size: 13px; margin-bottom: 4px;">Status</label>
      <select name="status" id="filter-status" style="width: 100%;">
        <option value="">All Statuses</option>
        {% for status in status_options %}
        <option value="{{ status }}" {% if filter_status and filter_status.lower() == status.lower() %}selected{% endif %}>
          {{ status.replace('_', ' ').title() }}
        </option>
        {% endfor %}
      </select>
    </div>

    <div class="form-field" style="margin: 0; flex: 1; min-width: 200px;">
      <label for="filter-property" style="font-size: 13px; margin-bottom: 4px;">Property</label>
      <select name="property" id="filter-property" style="width: 100%;">
        {% for prop in property_select_options %}
        <option value="{{ prop[0] }}" {% if filter_property and filter_property == prop[0] %}selected{% endif %}>
          {{ prop[1] }}
        </option>
        {% endfor %}
      </select>
    </div>

    <div class="form-field" style="margin: 0; flex: 1; min-width: 160px;">
      <label for="filter-assigned" style="font-size: 13px; margin-bottom: 4px;">Assignment</label>
      <select name="assigned" id="filter-assigned" style="width: 100%;">
        <option value="">All Items</option>
        <option value="assigned" {% if filter_assigned == 'assigned' %}selected{% endif %}>Assigned</option>
        <option value="unassigned" {% if filter_assigned == 'unassigned' %}selected{% endif %}>Unassigned</option>
      </select>
    </div>

    <div style="display: flex; gap: 8px;">
      <button type="submit" class="btn small primary">Apply Filters</button>
      {% if filter_status or filter_property or filter_assigned %}
      <a href="{{ url_for('inventory.list_signs', q=q or '') }}" class="btn small ghost">Clear Filters</a>
      {% endif %}
    </div>
  </form>
</div>

'''

    if 'id="advanced-filters"' not in content:
        # Find a good place to insert - look for the toolbar closing
        content = content.replace(
            '</div>\n</div>\n\n<div class="card table-card">',
            '</div>\n</div>\n\n' + filter_html + '<!-- Bulk Actions Toolbar -->\n<div class="bulkbar" id="bulk-toolbar">\n  <input type="checkbox" id="select-all-checkbox" onclick="toggleSelectAll(this)" style="margin: 0;">\n  <span id="bulk-count">0 selected</span>\n  <select id="bulk-action" class="form-control" style="max-width: 200px;">\n    <option value="">-- Select Action --</option>\n    <option value="delete">Delete Selected</option>\n    <option value="change-status">Change Status</option>\n    <option value="assign">Assign To...</option>\n  </select>\n  <button type="button" class="btn small primary" onclick="executeBulkAction()">Execute</button>\n  <button type="button" class="btn small ghost" onclick="clearSelection()">Cancel</button>\n</div>\n\n<div class="card table-card">'
        )

    # 3. Add checkbox column to table header
    if 'th-select-all' not in content:
        content = content.replace(
            '''<thead>
        <tr>
          <th>Label / Type</th>''',
            '''<thead>
        <tr>
          <th class="select-col"><input type="checkbox" id="th-select-all" onclick="toggleSelectAll(this)" style="margin: 0;"></th>
          <th>Label / Type</th>'''
        )

    # 4. Add checkbox to table rows
    if 'class="item-checkbox"' not in content:
        content = content.replace(
            '''{% for sign in signs %}
          {% set status_lower = (sign.status or '')|lower %}
          <tr>''',
            '''{% for sign in signs %}
          {% set status_lower = (sign.status or '')|lower %}
          <tr data-item-id="{{ sign.id }}" data-item-label="{{ sign.label }}">
            <td class="select-col">
              <input type="checkbox" class="item-checkbox" value="{{ sign.id }}" onchange="updateBulkToolbar()" style="margin: 0;">
            </td>'''
        )

    # 5. Add CSS for bulk operations
    bulk_css = '''
  .bulkbar {
    display: none;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border-radius: 12px;
    border: 1px solid var(--color-border);
    background: rgba(229, 57, 53, 0.08);
    color: var(--color-text);
    margin-bottom: 18px;
  }
  .bulkbar.show { display: flex; }
  .select-col { width: 40px; }
'''

    if '<style>' in content and '.bulkbar' not in content:
        content = content.replace('<style>', '<style>' + bulk_css)
    elif '<style>' not in content:
        content = content.replace('{% block content %}', '''{% block content %}
<style>''' + bulk_css + '''
</style>
''')

    # 6. Add JavaScript functions
    js_code = '''

  // === Filter and Bulk Operations ===

  function toggleFilters() {
    const filtersDiv = document.getElementById('advanced-filters');
    if (filtersDiv.style.display === 'none' || filtersDiv.style.display === '') {
      filtersDiv.style.display = 'block';
    } else {
      filtersDiv.style.display = 'none';
    }
  }

  function getSelectedItems() {
    const checkboxes = document.querySelectorAll('.item-checkbox:checked');
    return Array.from(checkboxes).map(cb => cb.value);
  }

  function updateBulkToolbar() {
    const selectedIds = getSelectedItems();
    const toolbar = document.getElementById('bulk-toolbar');
    const countSpan = document.getElementById('bulk-count');
    const selectAllCheckbox = document.getElementById('select-all-checkbox');
    const thSelectAll = document.getElementById('th-select-all');

    if (selectedIds.length > 0) {
      toolbar.classList.add('show');
      countSpan.textContent = `${selectedIds.length} selected`;
    } else {
      toolbar.classList.remove('show');
      countSpan.textContent = '0 selected';
    }

    const allCheckboxes = document.querySelectorAll('.item-checkbox');
    const allChecked = allCheckboxes.length > 0 && selectedIds.length === allCheckboxes.length;
    if (selectAllCheckbox) selectAllCheckbox.checked = allChecked;
    if (thSelectAll) thSelectAll.checked = allChecked;
  }

  function toggleSelectAll(checkbox) {
    const checkboxes = document.querySelectorAll('.item-checkbox');
    checkboxes.forEach(cb => {
      cb.checked = checkbox.checked;
    });
    updateBulkToolbar();
  }

  function clearSelection() {
    const checkboxes = document.querySelectorAll('.item-checkbox');
    checkboxes.forEach(cb => {
      cb.checked = false;
    });
    updateBulkToolbar();
  }

  function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }

  async function executeBulkAction() {
    const selectedIds = getSelectedItems();
    if (selectedIds.length === 0) {
      alert('Please select at least one item.');
      return;
    }

    const action = document.getElementById('bulk-action').value;
    if (!action) {
      alert('Please select an action.');
      return;
    }

    if (action === 'delete') {
      if (!confirm(`Are you sure you want to delete ${selectedIds.length} item(s)? This cannot be undone.`)) {
        return;
      }
      await bulkDelete(selectedIds);
    } else if (action === 'change-status') {
      const newStatus = prompt('Enter new status (available, assigned, checked_out, maintenance, retired):');
      if (newStatus) {
        await bulkUpdateStatus(selectedIds, newStatus);
      }
    } else if (action === 'assign') {
      const assignTo = prompt('Enter person to assign to (leave blank to unassign):');
      if (assignTo !== null) {
        await bulkAssign(selectedIds, assignTo);
      }
    }
  }

  async function bulkDelete(itemIds) {
    try {
      const response = await fetch('/inventory/bulk/delete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': getCsrfToken()
        },
        body: new URLSearchParams({
          item_ids: itemIds.join(','),
          item_type: 'sign'
        })
      });

      const data = await response.json();
      if (data.success) {
        alert(data.message);
        window.location.reload();
      } else {
        alert('Error: ' + data.error);
      }
    } catch (error) {
      alert('Error performing bulk delete: ' + error);
    }
  }

  async function bulkUpdateStatus(itemIds, newStatus) {
    try {
      const response = await fetch('/inventory/bulk/update_status', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': getCsrfToken()
        },
        body: new URLSearchParams({
          item_ids: itemIds.join(','),
          status: newStatus
        })
      });

      const data = await response.json();
      if (data.success) {
        alert(data.message);
        window.location.reload();
      } else {
        alert('Error: ' + data.error);
      }
    } catch (error) {
      alert('Error performing bulk status update: ' + error);
    }
  }

  async function bulkAssign(itemIds, assignTo) {
    try {
      const response = await fetch('/inventory/bulk/assign', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': getCsrfToken()
        },
        body: new URLSearchParams({
          item_ids: itemIds.join(','),
          assigned_to: assignTo
        })
      });

      const data = await response.json();
      if (data.success) {
        alert(data.message);
        window.location.reload();
      } else {
        alert('Error: ' + data.error);
      }
    } catch (error) {
      alert('Error performing bulk assign: ' + error);
    }
  }
'''

    if '</script>' in content and 'function toggleFilters' not in content:
        # Find the last </script> before {% endblock %}
        parts = content.rsplit('</script>', 1)
        if len(parts) == 2:
            content = parts[0] + js_code + '\n</script>' + parts[1]
    elif '<script>' not in content:
        content = content.replace('{% endblock %}', '<script>' + js_code + '\n</script>\n{% endblock %}')

    # Write back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"[OK] Updated {file_path}")


if __name__ == '__main__':
    print("Adding advanced filtering and bulk operations to templates...")
    add_filters_and_bulk_to_lockboxes()
    add_filters_and_bulk_to_signs()
    print("\n[SUCCESS] All templates updated successfully!")
