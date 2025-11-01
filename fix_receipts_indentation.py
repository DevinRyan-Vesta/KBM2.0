#!/usr/bin/env python3
"""Fix indentation in receipts page code"""

views_path = "inventory/views.py"
with open(views_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix the indentation issue around line 2098
fixed = False
for i in range(len(lines)):
    # Look for the incorrectly indented comment
    if i < len(lines) and lines[i].strip() == '# Show 10 most recent receipts by default when no search query':
        # Check if it needs fixing (should have 8 spaces, not 4)
        if not lines[i].startswith('        #'):
            lines[i] = '        # Show 10 most recent receipts by default when no search query\n'
            # Also fix the next few lines that might have wrong indentation
            if i+1 < len(lines) and lines[i+1].strip().startswith('results ='):
                lines[i+1] = '        results = tenant_query(ItemCheckout).order_by(\n'
            if i+2 < len(lines) and 'checked_out_at.desc()' in lines[i+2]:
                lines[i+2] = '            ItemCheckout.checked_out_at.desc()\n'
            if i+3 < len(lines) and ').limit(10)' in lines[i+3]:
                lines[i+3] = '        ).limit(10).all()\n'
            fixed = True
            break

if fixed:
    with open(views_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f"[OK] Fixed indentation in {views_path}")
else:
    print(f"[OK] Indentation already correct or could not find target lines in {views_path}")

print("\n[OK] Receipts page fix complete!")
