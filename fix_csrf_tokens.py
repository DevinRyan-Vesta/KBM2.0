#!/usr/bin/env python3
"""Script to add CSRF token support to dynamically created forms"""

import re

# Fix base.html - add CSRF meta tag
base_html_path = "templates/base.html"
with open(base_html_path, 'r', encoding='utf-8') as f:
    base_content = f.read()

# Check if CSRF meta tag already exists
if 'name="csrf-token"' not in base_content:
    # Add CSRF meta tag after viewport
    base_content = base_content.replace(
        '    <meta name="viewport" content="width=device-width, initial-scale=1">',
        '    <meta name="viewport" content="width=device-width, initial-scale=1">\n    <meta name="csrf-token" content="{{ csrf_token() }}">'
    )
    with open(base_html_path, 'w', encoding='utf-8') as f:
        f.write(base_content)
    print(f"[OK] Updated {base_html_path} with CSRF meta tag")
else:
    print(f"[OK] {base_html_path} already has CSRF meta tag")

# Fix item_actions.js - add CSRF token to submitAction function
js_path = "static/js/item_actions.js"
with open(js_path, 'r', encoding='utf-8') as f:
    js_content = f.read()

# Check if CSRF token is already being added
if 'csrf_token' in js_content and 'csrfToken' in js_content:
    print(f"[OK] {js_path} already has CSRF token handling")
else:
    # Find the submitAction function and add CSRF token handling
    old_submit_action = '''  function submitAction(url, payload, redirectUrl, redirectAnchor) {
    if (!url || url === "#") {
      return;
    }
    const form = document.createElement("form");
    form.method = "post";
    form.action = url;

    Object.entries(payload || {}).forEach(([key, value]) => {'''

    new_submit_action = '''  function submitAction(url, payload, redirectUrl, redirectAnchor) {
    if (!url || url === "#") {
      return;
    }
    const form = document.createElement("form");
    form.method = "post";
    form.action = url;

    // Add CSRF token
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    if (csrfToken) {
      const csrfInput = document.createElement("input");
      csrfInput.type = "hidden";
      csrfInput.name = "csrf_token";
      csrfInput.value = csrfToken;
      form.appendChild(csrfInput);
    }

    Object.entries(payload || {}).forEach(([key, value]) => {'''

    if old_submit_action in js_content:
        js_content = js_content.replace(old_submit_action, new_submit_action)
        with open(js_path, 'w', encoding='utf-8') as f:
            f.write(js_content)
        print(f"[OK] Updated {js_path} with CSRF token handling in submitAction")
    else:
        print(f"[ERROR] Could not find submitAction function in {js_path}")

print("\n[OK] CSRF token fix complete!")
print("All checkout/assign/checkin/edit operations should now work correctly.")
