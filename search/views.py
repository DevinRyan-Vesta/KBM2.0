# search/views.py
"""Global cross-entity search.

Two endpoints:
  GET /search/suggest?q=...  -> JSON, top-N matches across types (autocomplete)
  GET /search?q=...          -> HTML page, all matches grouped by type

Search covers items (lockboxes/keys/signs), properties, contacts, smart locks,
and receipts (item checkouts).
"""
from flask import Blueprint, jsonify, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import or_

from middleware.tenant_middleware import tenant_required
from utilities.tenant_helpers import tenant_query
from utilities.database import (
    Item,
    Property,
    Contact,
    SmartLock,
    ItemCheckout,
)

search_bp = Blueprint("search", __name__, template_folder="../templates")


# Per-type cap for the suggest dropdown — keeps the JSON payload small and the
# UI scannable. The full search page uses larger caps.
SUGGEST_PER_TYPE = 4
SEARCH_PER_TYPE = 25


def _item_type_kind(item: Item) -> str:
    """Return the lowercase entity kind for an Item, used for icons & labels."""
    t = (item.type or "").lower()
    if t == "lockbox":
        return "lockbox"
    if t == "key":
        return "key"
    if t == "sign":
        return "sign"
    return "item"


def _item_subtitle(item: Item) -> str:
    parts = []
    if item.custom_id:
        parts.append(item.custom_id)
    if item.address:
        parts.append(item.address)
    elif item.location:
        parts.append(item.location)
    if item.status:
        parts.append(item.status)
    return " · ".join(parts)


def _search_items(like: str, limit: int):
    return (
        tenant_query(Item)
        .filter(
            or_(
                Item.label.ilike(like),
                Item.custom_id.ilike(like),
                Item.address.ilike(like),
                Item.location.ilike(like),
                Item.key_hook_number.ilike(like),
                Item.keycode.ilike(like),
                Item.code_current.ilike(like),
                Item.supra_id.ilike(like),
                Item.assigned_to.ilike(like),
            )
        )
        .order_by(Item.label.asc())
        .limit(limit)
        .all()
    )


def _search_properties(like: str, limit: int):
    return (
        tenant_query(Property)
        .filter(
            or_(
                Property.name.ilike(like),
                Property.address_line1.ilike(like),
                Property.address_line2.ilike(like),
                Property.city.ilike(like),
                Property.postal_code.ilike(like),
            )
        )
        .order_by(Property.name.asc())
        .limit(limit)
        .all()
    )


def _search_contacts(like: str, limit: int):
    return (
        tenant_query(Contact)
        .filter(
            or_(
                Contact.name.ilike(like),
                Contact.company.ilike(like),
                Contact.email.ilike(like),
                Contact.phone.ilike(like),
            )
        )
        .order_by(Contact.name.asc())
        .limit(limit)
        .all()
    )


def _search_smartlocks(like: str, limit: int):
    return (
        tenant_query(SmartLock)
        .filter(
            or_(
                SmartLock.label.ilike(like),
                SmartLock.code.ilike(like),
                SmartLock.provider.ilike(like),
            )
        )
        .order_by(SmartLock.label.asc())
        .limit(limit)
        .all()
    )


def _search_receipts(query: str, like: str, limit: int):
    """Receipts are ItemCheckout rows. Match on RCP## / id / who / item label."""
    receipt_id = None
    candidate = query[3:] if query.upper().startswith("RCP") else query
    try:
        receipt_id = int(candidate)
    except ValueError:
        pass

    filters = [
        ItemCheckout.checked_out_to.ilike(like),
        ItemCheckout.address.ilike(like),
        Item.label.ilike(like),
        Item.custom_id.ilike(like),
    ]
    if receipt_id is not None:
        filters.append(ItemCheckout.id == receipt_id)

    return (
        tenant_query(ItemCheckout)
        .outerjoin(Item, ItemCheckout.item_id == Item.id)
        .filter(or_(*filters))
        .order_by(ItemCheckout.checked_out_at.desc())
        .limit(limit)
        .all()
    )


def _serialize_item(item: Item) -> dict:
    kind = _item_type_kind(item)
    return {
        "type": kind,
        "type_label": kind.capitalize(),
        "label": item.label,
        "subtitle": _item_subtitle(item),
        "url": url_for("inventory.item_details", item_id=item.id),
    }


def _serialize_property(prop: Property) -> dict:
    return {
        "type": "property",
        "type_label": "Property",
        "label": prop.name,
        "subtitle": prop.address_line1 or "",
        "url": url_for("properties.property_detail", property_id=prop.id),
    }


def _serialize_contact(contact: Contact) -> dict:
    subtitle_parts = []
    if contact.company:
        subtitle_parts.append(contact.company)
    if contact.email:
        subtitle_parts.append(contact.email)
    elif contact.phone:
        subtitle_parts.append(contact.phone)
    return {
        "type": "contact",
        "type_label": "Contact",
        "label": contact.name,
        "subtitle": " · ".join(subtitle_parts),
        "url": url_for("contacts.contact_detail", contact_id=contact.id),
    }


def _serialize_smartlock(lock: SmartLock) -> dict:
    parts = []
    if lock.provider:
        parts.append(lock.provider)
    if lock.property:
        parts.append(lock.property.name)
    return {
        "type": "smartlock",
        "type_label": "Smart Lock",
        "label": lock.label,
        "subtitle": " · ".join(parts),
        "url": url_for("smartlocks.smartlock_detail", lock_id=lock.id),
    }


def _serialize_receipt(checkout: ItemCheckout) -> dict:
    item_label = checkout.item.label if checkout.item else "Item not found"
    return {
        "type": "receipt",
        "type_label": "Receipt",
        "label": f"RCP{checkout.id:06d} — {item_label}",
        "subtitle": f"To {checkout.checked_out_to}" if checkout.checked_out_to else "",
        "url": url_for("inventory.checkout_receipt", checkout_id=checkout.id),
    }


@search_bp.get("/search/suggest")
@login_required
@tenant_required
def suggest():
    """Autocomplete endpoint — top-N matches across all types as flat JSON."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"results": [], "query": q})

    like = f"%{q}%"

    results = []
    results.extend(_serialize_item(i) for i in _search_items(like, SUGGEST_PER_TYPE))
    results.extend(_serialize_property(p) for p in _search_properties(like, SUGGEST_PER_TYPE))
    results.extend(_serialize_contact(c) for c in _search_contacts(like, SUGGEST_PER_TYPE))
    results.extend(_serialize_smartlock(s) for s in _search_smartlocks(like, SUGGEST_PER_TYPE))
    results.extend(_serialize_receipt(r) for r in _search_receipts(q, like, SUGGEST_PER_TYPE))

    return jsonify({"results": results, "query": q})


@search_bp.get("/search")
@login_required
@tenant_required
def search():
    """Full search page — sections per entity type."""
    q = (request.args.get("q") or "").strip()

    if not q:
        return render_template("search_results.html", query=q, sections=[], total=0)

    like = f"%{q}%"
    sections = [
        {
            "title": "Inventory Items",
            "kind": "item",
            "results": [_serialize_item(i) for i in _search_items(like, SEARCH_PER_TYPE)],
        },
        {
            "title": "Properties",
            "kind": "property",
            "results": [_serialize_property(p) for p in _search_properties(like, SEARCH_PER_TYPE)],
        },
        {
            "title": "Contacts",
            "kind": "contact",
            "results": [_serialize_contact(c) for c in _search_contacts(like, SEARCH_PER_TYPE)],
        },
        {
            "title": "Smart Locks",
            "kind": "smartlock",
            "results": [_serialize_smartlock(s) for s in _search_smartlocks(like, SEARCH_PER_TYPE)],
        },
        {
            "title": "Receipts",
            "kind": "receipt",
            "results": [_serialize_receipt(r) for r in _search_receipts(q, like, SEARCH_PER_TYPE)],
        },
    ]
    total = sum(len(s["results"]) for s in sections)

    return render_template("search_results.html", query=q, sections=sections, total=total)
