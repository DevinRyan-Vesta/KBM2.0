#!/usr/bin/env python3
"""Script to fix receipts page to show 10 most recent by default"""

# Fix inventory/views.py - modify receipt_lookup to show recent receipts by default
views_path = "inventory/views.py"
with open(views_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the receipt_lookup function and modify it
old_receipt_lookup = '''def receipt_lookup():
    """Receipt lookup page with barcode scanner support"""
    query = (request.args.get("q") or "").strip()
    results = []

    if query:
        # Try to extract receipt ID from barcode (RCP000001 format)
        receipt_id = None
        if query.upper().startswith("RCP"):
            try:
                receipt_id = int(query[3:])
            except ValueError:
                pass
        else:
            # Try direct ID
            try:
                receipt_id = int(query)
            except ValueError:
                pass

        # Build search filter
        filters = []
        if receipt_id:
            filters.append(ItemCheckout.id == receipt_id)

        # Also search by checked_out_to name
        if query:
            like = f"%{query}%"
            filters.append(ItemCheckout.checked_out_to.ilike(like))

        if filters:
            from sqlalchemy import or_
            results = tenant_query(ItemCheckout).filter(or_(*filters)).order_by(
                ItemCheckout.checked_out_at.desc()
            ).limit(50).all()

    return render_template("receipt_lookup.html", results=results, query=query)'''

new_receipt_lookup = '''def receipt_lookup():
    """Receipt lookup page with barcode scanner support"""
    query = (request.args.get("q") or "").strip()
    results = []

    if query:
        # Try to extract receipt ID from barcode (RCP000001 format)
        receipt_id = None
        if query.upper().startswith("RCP"):
            try:
                receipt_id = int(query[3:])
            except ValueError:
                pass
        else:
            # Try direct ID
            try:
                receipt_id = int(query)
            except ValueError:
                pass

        # Build search filter
        filters = []
        if receipt_id:
            filters.append(ItemCheckout.id == receipt_id)

        # Also search by checked_out_to name
        if query:
            like = f"%{query}%"
            filters.append(ItemCheckout.checked_out_to.ilike(like))

        if filters:
            from sqlalchemy import or_
            results = tenant_query(ItemCheckout).filter(or_(*filters)).order_by(
                ItemCheckout.checked_out_at.desc()
            ).limit(50).all()
    else:
        # Show 10 most recent receipts by default when no search query
        results = tenant_query(ItemCheckout).order_by(
            ItemCheckout.checked_out_at.desc()
        ).limit(10).all()

    return render_template("receipt_lookup.html", results=results, query=query)'''

if old_receipt_lookup in content:
    content = content.replace(old_receipt_lookup, new_receipt_lookup)
    with open(views_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[OK] Updated receipt_lookup to show 10 most recent by default")
else:
    print(f"[ERROR] Could not find receipt_lookup function in {views_path}")

print("\n[OK] Receipts page fix complete!")
print("Receipts page now shows 10 most recent receipts when first loaded.")
