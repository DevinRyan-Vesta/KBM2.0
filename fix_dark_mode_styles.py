#!/usr/bin/env python3
"""Script to fix dark mode visibility issues"""

import re

# Fix 1: Add proper dropdown styling to keys.html and other pages
files_with_dropdowns = [
    "templates/keys.html",
    "templates/lockboxes.html",
    "templates/signs.html"
]

dropdown_fix = """
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
  }"""

for file_path in files_with_dropdowns:
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()

        # Find and replace the old dropdown menu styles
        old_pattern = r'/\* Export dropdown menu \*/\s*\.dropdown-menu\s*{[^}]+}[^<]*\.dropdown-menu a:hover\s*{[^}]+}'

        if re.search(old_pattern, content, re.DOTALL):
            content = re.sub(old_pattern, dropdown_fix, content, flags=re.DOTALL)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[OK] Fixed dropdown styles in {file_path}")
        else:
            print(f"[SKIP] No dropdown styles found in {file_path}")
    except FileNotFoundError:
        print(f"[SKIP] {file_path} not found")

# Fix 2: Add better link visibility to base.html
base_html_path = "templates/base.html"
with open(base_html_path, 'r', encoding='utf-8') as f:
    base_content = f.read()

# Check if link styles are already improved
if 'a {' not in base_content or 'a:visited' not in base_content:
    # Find the spot after the body styles and add link styles
    link_styles = """
      /* Link Styles */
      a {
        color: var(--color-accent);
        text-decoration: underline;
        text-decoration-color: rgba(229, 57, 53, 0.3);
        transition: all 0.2s ease;
      }

      body.light a {
        color: #c62828;
        text-decoration-color: rgba(198, 40, 40, 0.3);
      }

      a:hover {
        color: var(--color-accent);
        text-decoration-color: var(--color-accent);
      }

      a:visited {
        color: #ff6b9d;
        text-decoration-color: rgba(255, 107, 157, 0.3);
      }

      body.light a:visited {
        color: #ad1457;
        text-decoration-color: rgba(173, 20, 87, 0.3);
      }

      /* Keep existing link overrides working */
      .nav-links a,
      .btn,
      table a {
        text-decoration: none;
      }
"""

    # Find where to insert (after body styles)
    insert_marker = "body {"
    if insert_marker in base_content:
        # Find the end of the body block
        body_start = base_content.find(insert_marker)
        body_end = base_content.find("}", body_start) + 1

        # Insert link styles after body styles
        base_content = base_content[:body_end] + "\n" + link_styles + base_content[body_end:]

        with open(base_html_path, 'w', encoding='utf-8') as f:
            f.write(base_content)
        print(f"[OK] Added improved link styles to {base_html_path}")
    else:
        print(f"[ERROR] Could not find insertion point in {base_html_path}")
else:
    print(f"[OK] {base_html_path} already has link styles")

print("\n[OK] Dark mode fixes complete!")
print("Dark mode improvements:")
print("  - Export dropdown now visible in dark mode")
print("  - Links have better contrast and visibility")
print("  - Visited links have distinct color")
