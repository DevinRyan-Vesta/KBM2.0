#!/usr/bin/env python3
"""Test if the app starts without errors."""

from app_multitenant import app

print("[OK] App loads successfully")
print("\nRegistered blueprints:")
for bp_name in app.blueprints:
    bp = app.blueprints[bp_name]
    print(f"  - {bp_name}")

print("\nRegistered routes (first 20):")
for i, rule in enumerate(app.url_map.iter_rules()):
    if i >= 20:
        print(f"  ... and {len(list(app.url_map.iter_rules())) - 20} more")
        break
    print(f"  {rule.rule} -> {rule.endpoint}")

print("\n[OK] All checks passed!")
