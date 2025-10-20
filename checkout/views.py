# checkout/views.py
from flask import Blueprint, render_template, jsonify, abort, request
from flask_login import login_required
from utilities.database import db, Item, ItemCheckout

checkout_bp = Blueprint(
    "checkout",
    __name__,
    template_folder="../templates",
    static_folder="../static"
)


@checkout_bp.get("/")
@login_required
def start():
    return render_template("checkout_start.html")


@checkout_bp.get("/ping")
def checkout_ping():
    return "Checkout blueprint is alive", 200


# API route to lookup items by ID (numeric or custom)
@checkout_bp.get("/api/items/<item_id>")
@login_required
def api_get_item(item_id):
    """API endpoint to get item details by ID (numeric or custom_id) for the checkout page"""
    # Try to find by custom_id first
    item = Item.query.filter_by(custom_id=item_id).first()

    # If not found, try numeric ID
    if not item and item_id.isdigit():
        item = db.session.get(Item, int(item_id))

    if not item:
        abort(404)
    return jsonify(item.to_dict())


# API route for autocomplete search
@checkout_bp.get("/api/items/search")
@login_required
def api_search_items():
    """API endpoint for autocomplete search"""
    query = request.args.get('q', '').strip()

    if not query or len(query) < 1:
        return jsonify([])

    # Search by custom_id, label, address
    like_pattern = f"%{query}%"

    items = Item.query.filter(
        db.or_(
            Item.custom_id.ilike(like_pattern),
            Item.label.ilike(like_pattern),
            Item.address.ilike(like_pattern)
        )
    ).limit(10).all()

    return jsonify([{
        'custom_id': item.custom_id,
        'label': item.label,
        'type': item.type,
        'address': item.address,
        'status': item.status,
        'display': f"{item.custom_id} - {item.label}" + (f" ({item.address})" if item.address else "")
    } for item in items])


# API route to search items by person name
@checkout_bp.get("/api/items/by-person")
@login_required
def api_search_by_person():
    """API endpoint to find all items checked out to or assigned to a person"""
    name = request.args.get('name', '').strip()

    if not name or len(name) < 2:
        return jsonify({"items": []})

    results = []
    like_pattern = f"%{name}%"

    # Find active checkouts for this person
    active_checkouts = ItemCheckout.query.filter(
        ItemCheckout.is_active == True,
        ItemCheckout.checked_out_to.ilike(like_pattern)
    ).all()

    # Add items from active checkouts
    for checkout in active_checkouts:
        item = checkout.item
        if item:
            results.append({
                'id': item.id,
                'custom_id': item.custom_id,
                'label': item.label,
                'type': item.type,
                'status': 'checked_out',
                'address': item.address,
                'location': item.location,
                'purpose': checkout.purpose,
                'checkout_quantity': checkout.quantity,
                'checkout_id': checkout.id,
                'checked_out_at': checkout.checked_out_at.strftime('%Y-%m-%d %H:%M') if checkout.checked_out_at else None,
            })

    # Also find items assigned to this person (but not in active checkouts)
    assigned_items = Item.query.filter(
        Item.assigned_to.ilike(like_pattern),
        Item.status == 'assigned'
    ).all()

    # Add assigned items that aren't already in results
    checkout_item_ids = {r['id'] for r in results}
    for item in assigned_items:
        if item.id not in checkout_item_ids:
            results.append({
                'id': item.id,
                'custom_id': item.custom_id,
                'label': item.label,
                'type': item.type,
                'status': 'assigned',
                'address': item.address,
                'location': item.location,
                'purpose': None,
                'checkout_quantity': None,
                'checkout_id': None,
                'checked_out_at': None,
            })

    return jsonify({"items": results})
