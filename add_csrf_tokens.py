#!/usr/bin/env python3
"""
Script to automatically add CSRF tokens to all POST forms in templates.
"""

import os
import re
from pathlib import Path

def add_csrf_to_form(content, form_match):
    """Add CSRF token to a form if it doesn't already have one."""
    form_tag = form_match.group(0)

    # Skip if already has CSRF token
    if 'csrf_token' in form_tag:
        return None

    # Skip GET forms (they don't need CSRF)
    if 'method="GET"' in form_tag or 'method="get"' in form_tag:
        return None

    # Skip forms that are just for display/modals without actual submission
    if 'id="action-modal-form"' in form_tag or 'id="item-action-modal-form"' in form_tag:
        return None

    # Find the end of the opening form tag
    form_end = form_tag.find('>')
    if form_end == -1:
        return None

    # Add CSRF token right after opening form tag
    csrf_field = '\n        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>'
    new_form = form_tag[:form_end + 1] + csrf_field

    return new_form

def process_template(filepath):
    """Process a single template file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        modified = False

        # Find all form tags (including multiline)
        pattern = r'<form[^>]*>'

        for match in re.finditer(pattern, content, re.IGNORECASE):
            new_form = add_csrf_to_form(content, match)
            if new_form:
                content = content.replace(match.group(0), new_form, 1)
                modified = True
                print(f"  [+] Added CSRF token to form in {filepath.name}")

        if modified:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True

        return False

    except Exception as e:
        print(f"  [!] Error processing {filepath}: {e}")
        return False

def main():
    """Main function to process all templates."""
    templates_dir = Path('templates')

    if not templates_dir.exists():
        print("Error: templates directory not found")
        return

    print("Adding CSRF tokens to all POST forms...\n")

    total_files = 0
    modified_files = 0

    # Process all HTML files recursively
    for html_file in templates_dir.rglob('*.html'):
        total_files += 1
        if process_template(html_file):
            modified_files += 1

    print(f"\n{'='*50}")
    print(f"Processed {total_files} template files")
    print(f"Modified {modified_files} files")
    print(f"{'='*50}\n")
    print("[SUCCESS] CSRF tokens added successfully!")
    print("\nNext steps:")
    print("1. Rebuild Docker: docker-compose down && docker-compose build && docker-compose up -d")
    print("2. Test login and other forms")

if __name__ == '__main__':
    main()
