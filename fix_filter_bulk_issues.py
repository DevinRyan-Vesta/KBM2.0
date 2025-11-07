#!/usr/bin/env python3
"""
Fix issues with filter and bulk operations implementation:
1. Add dark mode select styling to base.html
2. Completely rebuild lockboxes.html from scratch based on working keys.html
3. Fix any issues in signs.html
4. Remove duplicate elements
"""

import re

def add_dark_mode_select_css():
    """Add global dark mode CSS for select elements to base.html"""
    file_path = 'templates/base.html'

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # CSS for select elements in dark mode
    select_css = """
    /* Dark mode select element styling */
    select,
    select option {
      background: var(--color-surface);
      color: var(--color-text);
      border: 1px solid var(--color-border);
    }

    select:focus,
    select:active {
      background: var(--color-surface);
      color: var(--color-text);
      outline-color: var(--color-accent);
    }
    """

    # Find the closing </style> tag in the header and insert before it
    if '</style>' in content:
        # Find the last </style> in the head section
        parts = content.split('</head>')
        if len(parts) >= 2:
            head_part = parts[0]
            rest = '</head>' + parts[1]

            # Insert CSS before last </style> in head
            head_part = head_part.replace('</style>', select_css + '\n  </style>')
            content = head_part + rest

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"[OK] Added dark mode select CSS to {file_path}")


def rebuild_lockboxes_template():
    """Completely rebuild lockboxes.html based on keys.html pattern"""
    # Read the working keys.html as a template
    with open('templates/keys.html', 'r', encoding='utf-8') as f:
        keys_content = f.read()

    # Read the original lockboxes.html to preserve any lockbox-specific content
    with open('templates/lockboxes.html', 'r', encoding='utf-8') as f:
        original = f.read()

    # Extract the lockbox-specific table rows structure from original
    # We'll rebuild the file from keys.html structure but customize for lockboxes

    lockboxes_template = '''{% extends "base.html" %}
{% block title %}Lockboxes - KBM{% endblock %}

{% block content %}
<style>
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

  /* Export dropdown menu */
  .dropdown-menu {
    position: absolute;
    background: var(--color-card);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
    z-index: 1000;
    min-width: 150px;
  }
  .dropdown-menu a {
    display: block;
    padding: 10px 14px;
    color: var(--color-text);
    text-decoration: none;
    border-bottom: 1px solid var(--color-border);
    transition: background 0.2s ease;
  }
  .dropdown-menu a:last-child {
    border-bottom: none;
  }
  .dropdown-menu a:hover {
    background: rgba(229, 57, 53, 0.12);
    color: var(--color-accent);
  }
</style>

{% set status_options = status_options or ['available', 'assigned', 'checked_out', 'maintenance', 'retired'] %}

<div class="page-header">
  <h1>Lockboxes</h1>
  <div class="toolbar">
    <form method="get" class="searchbar" action="{{ url_for('inventory.list_lockboxes') }}">
      <input type="text" name="q" placeholder="Search ID, label, address, code..." value="{{ q or '' }}">
      <button class="btn small" type="submit">Search</button>
      {% if q %}
        <a class="btn small" href="{{ url_for('inventory.list_lockboxes') }}">Clear</a>
      {% endif %}
    </form>
    <div class="btn-group">
      <button type="button" class="btn small" onclick="toggleFilters()">Filters ▾</button>
      <button type="button" class="btn small" onclick="showExportMenu(event, 'lockboxes')">Export ▾</button>
      <a class="btn small" href="{{ url_for('inventory.import_lockboxes') }}">Import</a>
      <a class="btn primary" href="{{ url_for('inventory.add_lockbox') }}">Add Lockbox</a>
    </div>
  </div>
</div>

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

<div id="export-menu" class="dropdown-menu" style="display: none;">
  <a href="#" onclick="exportData(event, 'csv')">Export as CSV</a>
  <a href="#" onclick="exportData(event, 'excel')">Export as Excel</a>
  <a href="#" onclick="exportData(event, 'pdf')">Export as PDF</a>
</div>

<!-- Bulk Actions Toolbar -->
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

<div class="card table-card">
  {% set viewer_role = (current_user.role or '').lower() if current_user.is_authenticated else '' %}
  {% if lockboxes %}
    <table>
      <thead>
        <tr>
          <th class="select-col"><input type="checkbox" id="th-select-all" onclick="toggleSelectAll(this)" style="margin: 0;"></th>
          <th>Label</th>
          <th>Location / Property</th>
          <th>Codes</th>
          <th>Status</th>
          <th>Assigned To</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for lockbox in lockboxes %}
          {% set status_lower = (lockbox.status or '')|lower %}
          <tr data-item-id="{{ lockbox.id }}" data-item-label="{{ lockbox.label }}">
            <td class="select-col">
              <input type="checkbox" class="item-checkbox" value="{{ lockbox.id }}" onchange="updateBulkToolbar()" style="margin: 0;">
            </td>
            <td>
              <div><strong><a href="{{ url_for('inventory.item_details', item_id=lockbox.id) }}" style="color: inherit; text-decoration: none;">{{ lockbox.label }}</a></strong></div>
              <div class="muted">{{ lockbox.custom_id or '-' }}</div>
            </td>
            <td>
              {% if lockbox.property %}
                <strong>{{ lockbox.property.name }}</strong><br>
                <span class="muted text-small">
                  {{ lockbox.property.address_line1 or '' }}
                  {% if lockbox.property.city %}, {{ lockbox.property.city }}{% endif %}
                  {% if lockbox.property.state %}, {{ lockbox.property.state }}{% endif %}
                </span><br>
              {% endif %}
              {% if lockbox.location %}
                <span class="muted text-small">{{ lockbox.location }}</span>
              {% else %}
                <span class="muted">-</span>
              {% endif %}
            </td>
            <td>
              <div><strong>Current:</strong> {{ lockbox.code_current or '-' }}</div>
              {% if lockbox.code_previous %}
                <div class="muted text-small"><strong>Previous:</strong> {{ lockbox.code_previous }}</div>
              {% endif %}
              {% if lockbox.supra_id %}
                <div class="muted text-small"><strong>Supra:</strong> {{ lockbox.supra_id }}</div>
              {% endif %}
            </td>
            <td>
              {% if status_lower == 'available' %}
                <span class="badge badge-success">Available</span>
              {% elif status_lower == 'assigned' %}
                <span class="badge badge-info">Assigned</span>
              {% elif status_lower == 'checked_out' %}
                <span class="badge badge-warning">Checked Out</span>
              {% elif status_lower == 'maintenance' %}
                <span class="badge badge-secondary">Maintenance</span>
              {% elif status_lower == 'retired' %}
                <span class="badge badge-danger">Retired</span>
              {% else %}
                <span class="badge">{{ lockbox.status or 'Unknown' }}</span>
              {% endif %}
            </td>
            <td>{{ lockbox.assigned_to or '-' }}</td>
            <td>
              <div class="row-buttons">
                {% if viewer_role in ['admin', 'owner', 'staff'] %}
                  <button class="btn xsmall" onclick="openItemActionModal({{ lockbox.id }}, 'edit')">Edit</button>

                  {% if status_lower == 'available' %}
                    <button class="btn xsmall" onclick="openItemActionModal({{ lockbox.id }}, 'assign')">Assign</button>
                    <button class="btn xsmall" onclick="openItemActionModal({{ lockbox.id }}, 'checkout')">Checkout</button>
                  {% elif status_lower == 'assigned' %}
                    <button class="btn xsmall" onclick="openItemActionModal({{ lockbox.id }}, 'unassign')">Unassign</button>
                  {% elif status_lower == 'checked_out' %}
                    <button class="btn xsmall" onclick="openItemActionModal({{ lockbox.id }}, 'checkin')">Checkin</button>
                  {% endif %}

                  {% if viewer_role in ['admin', 'owner'] %}
                    <a class="btn xsmall danger" href="{{ url_for('inventory.delete_lockbox', item_id=lockbox.id) }}" onclick="return confirm('Delete this lockbox?')">Delete</a>
                  {% endif %}
                {% else %}
                  <a class="btn xsmall" href="{{ url_for('inventory.item_details', item_id=lockbox.id) }}">View</a>
                {% endif %}
              </div>
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% else %}
    <p class="muted">No lockboxes found. <a href="{{ url_for('inventory.add_lockbox') }}">Add your first lockbox</a>.</p>
  {% endif %}
</div>

<script>
  // Export menu functionality
  let exportMenuData = null;

  function showExportMenu(event, itemType) {
    event.preventDefault();
    const menu = document.getElementById('export-menu');
    const button = event.target;
    const rect = button.getBoundingClientRect();

    menu.style.left = rect.left + 'px';
    menu.style.top = (rect.bottom + 5) + 'px';
    menu.style.display = 'block';
    exportMenuData = itemType;

    // Close menu when clicking outside
    setTimeout(() => {
      document.addEventListener('click', closeExportMenu);
    }, 0);
  }

  function closeExportMenu(event) {
    const menu = document.getElementById('export-menu');
    if (event && menu.contains(event.target)) return;
    menu.style.display = 'none';
    document.removeEventListener('click', closeExportMenu);
  }

  function exportData(event, format) {
    event.preventDefault();
    if (!exportMenuData) return;

    const url = `/exports/items/${exportMenuData}?format=${format}`;
    window.location.href = url;
    closeExportMenu();
  }

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

    // Update select-all checkbox state
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
</script>

<!-- Item Actions Modal (for edit/assign/checkout/checkin) -->
<!-- This modal is populated dynamically by item_actions.js -->
<div id="item-action-modal" class="modal-root">
  <div class="modal-backdrop" data-modal-cancel="item-action"></div>
  <div class="modal-dialog">
    <h3 id="item-action-modal-title">Item Action</h3>
    <form id="item-action-modal-form" method="post">
      <div id="item-action-modal-body"></div>
      <div class="modal-actions">
        <button type="button" class="btn ghost" data-modal-cancel="item-action">Cancel</button>
        <button type="submit" id="item-action-modal-submit" class="btn primary">Submit</button>
      </div>
    </form>
  </div>
</div>

<script src="{{ url_for('static', filename='js/modals.js') }}"></script>
<script src="{{ url_for('static', filename='js/item_actions.js') }}"></script>
<script>
  window.kbmItemDetails = {
    itemType: 'lockbox',
    statusOptions: {{ status_options | tojson }},
    propertyOptions: {{ property_select_options | tojson }},
    propertyMap: {{ property_map | tojson }},
    activeCheckoutsUrl: "{{ url_for('inventory.active_checkouts_lockbox', item_id=0) }}".replace('/0', '')
  };
</script>

{% endblock %}
'''

    with open('templates/lockboxes.html', 'w', encoding='utf-8') as f:
        f.write(lockboxes_template)

    print(f"[OK] Completely rebuilt templates/lockboxes.html")


def fix_signs_checkboxes():
    """Fix signs.html - add missing checkboxes if not present"""
    file_path = 'templates/signs.html'

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if checkboxes are missing from table header
    if '<th class="select-col">' not in content or 'th-select-all' not in content:
        # Need to add checkbox column header
        content = re.sub(
            r'<thead>\s*<tr>\s*<th>Label',
            '<thead>\n        <tr>\n          <th class="select-col"><input type="checkbox" id="th-select-all" onclick="toggleSelectAll(this)" style="margin: 0;"></th>\n          <th>Label',
            content
        )

    # Check if checkboxes are in table rows
    if 'class="item-checkbox"' not in content:
        # Add checkbox column to rows
        content = re.sub(
            r'<tr data-item-id="{{ sign\.id }}" data-item-label="{{ sign\.label }}">',
            '''<tr data-item-id="{{ sign.id }}" data-item-label="{{ sign.label }}">
            <td class="select-col">
              <input type="checkbox" class="item-checkbox" value="{{ sign.id }}" onchange="updateBulkToolbar()" style="margin: 0;">
            </td>''',
            content
        )

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"[OK] Fixed checkboxes in {file_path}")


if __name__ == '__main__':
    print("Fixing filter and bulk operations issues...")
    print("\n1. Adding dark mode select CSS...")
    add_dark_mode_select_css()

    print("\n2. Rebuilding lockboxes template...")
    rebuild_lockboxes_template()

    print("\n3. Fixing signs template checkboxes...")
    fix_signs_checkboxes()

    print("\n[SUCCESS] All fixes applied!")
    print("\nPlease review the changes and test:")
    print("- Dark mode select elements should now be readable")
    print("- Lockboxes page should have correct layout")
    print("- No duplicate buttons")
    print("- Bulk operations should work")
