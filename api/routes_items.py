"""Inventory items: CRUD plus checkout / checkin / assign actions.

The action endpoints mirror the web flows in inventory/views.py exactly —
same status transitions, same validation rules, same activity-log actions —
so records created via the API are indistinguishable from web activity.
"""

from flask import g, jsonify, request

from api import api_bp
from api.helpers import (
    api_tenant_required,
    clean_int,
    clean_str,
    error,
    get_json_body,
    list_response,
    paginate,
    parse_date,
    require_admin,
)
from utilities.database import (
    db,
    Contact,
    Item,
    ItemCheckout,
    Property,
    PropertyUnit,
    log_activity,
    utc_now,
)
from utilities.tenant_helpers import (
    get_tenant_session,
    tenant_add,
    tenant_commit,
    tenant_query,
)

ITEM_TYPES = ("Lockbox", "Key", "Sign")

# Fields writable via POST/PATCH, per type. Status and checkout counters are
# managed exclusively by the action endpoints.
COMMON_FIELDS = {"label", "location", "address", "assigned_to"}
TYPE_FIELDS = {
    "Lockbox": COMMON_FIELDS | {"code_current", "code_previous", "supra_id"},
    "Key": COMMON_FIELDS | {"key_hook_number", "keycode", "total_copies", "checkout_purpose", "master_key_id"},
    "Sign": COMMON_FIELDS | {"sign_subtype", "piece_type", "rider_text", "material", "condition"},
}
INT_FIELDS = {"total_copies", "master_key_id"}


def _get_item_or_404(item_ref: str) -> Item:
    """Look up an item by numeric id or by custom_id (e.g. 'KA042')."""
    item = None
    if item_ref.isdigit():
        item = get_tenant_session().get(Item, int(item_ref))
    if item is None:
        item = tenant_query(Item).filter(
            db.func.upper(Item.custom_id) == item_ref.upper()
        ).first()
    if item is None:
        raise error(404, "not_found", f"Item '{item_ref}' not found.")
    return item


def _validate_contact_id(raw) -> int | None:
    cid = clean_int(raw, "contact_id")
    if cid is None:
        return None
    contact = get_tenant_session().get(Contact, cid)
    if contact is None:
        raise error(400, "invalid_field", f"Contact {cid} not found.")
    return contact.id


def _resolve_property_refs(body):
    """Validate property_id / property_unit_id like the web assign forms do."""
    property_obj = None
    unit_obj = None
    pid = clean_int(body.get("property_id"), "property_id")
    uid = clean_int(body.get("property_unit_id"), "property_unit_id")
    if pid is not None:
        property_obj = get_tenant_session().get(Property, pid)
        if property_obj is None:
            raise error(400, "invalid_field", f"Property {pid} not found.")
    if uid is not None:
        unit_obj = get_tenant_session().get(PropertyUnit, uid)
        if unit_obj is None:
            raise error(400, "invalid_field", f"Property unit {uid} not found.")
        if property_obj and unit_obj.property_id != property_obj.id:
            raise error(400, "invalid_field", "Selected unit does not belong to the chosen property.")
        if property_obj is None:
            property_obj = unit_obj.property
    return property_obj, unit_obj


def _apply_writable_fields(item: Item, body: dict):
    allowed = TYPE_FIELDS[item.type]
    unknown = set(body.keys()) - allowed - {"type", "custom_id", "property_id", "property_unit_id"}
    if unknown:
        raise error(400, "unknown_fields",
                    f"Unknown or read-only field(s) for a {item.type}: {', '.join(sorted(unknown))}.")

    for field in allowed:
        if field not in body:
            continue
        if field in INT_FIELDS:
            value = clean_int(body.get(field), field)
            if field == "total_copies" and value is not None and value < 0:
                raise error(400, "invalid_field", "'total_copies' cannot be negative.")
            if field == "master_key_id" and value is not None:
                master = tenant_query(Item).filter_by(id=value, type="Key").first()
                if master is None:
                    raise error(400, "invalid_field", f"Master key {value} not found.")
                if master.id == item.id:
                    raise error(400, "invalid_field", "A key cannot be its own master key.")
            setattr(item, field, value)
        else:
            setattr(item, field, clean_str(body.get(field), field, 255))

    if "property_id" in body or "property_unit_id" in body:
        property_obj, unit_obj = _resolve_property_refs(body)
        if "property_id" in body:
            item.property = property_obj
        if "property_unit_id" in body:
            item.property_unit = unit_obj


# --- CRUD --------------------------------------------------------------------

@api_bp.get("/items")
@api_tenant_required
def list_items():
    query = tenant_query(Item)

    item_type = request.args.get("type")
    if item_type:
        if item_type not in ITEM_TYPES:
            raise error(400, "invalid_field", f"'type' must be one of: {', '.join(ITEM_TYPES)}.")
        query = query.filter(Item.type == item_type)

    status = request.args.get("status")
    if status:
        query = query.filter(Item.status == status)

    property_id = request.args.get("property_id", type=int)
    if property_id:
        query = query.filter(Item.property_id == property_id)

    assigned_to = request.args.get("assigned_to")
    if assigned_to:
        query = query.filter(Item.assigned_to.ilike(f"%{assigned_to}%"))

    q = request.args.get("q")
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(
            Item.custom_id.ilike(like),
            Item.label.ilike(like),
            Item.address.ilike(like),
            Item.location.ilike(like),
        ))

    query = query.order_by(Item.id.asc())
    rows, meta = paginate(query)
    return list_response("items", rows, meta)


@api_bp.post("/items")
@api_tenant_required
def create_item():
    body = get_json_body()

    item_type = clean_str(body.get("type"), "type", 50)
    if item_type not in ITEM_TYPES:
        raise error(400, "invalid_field", f"'type' is required and must be one of: {', '.join(ITEM_TYPES)}.")

    label = clean_str(body.get("label"), "label", 120)
    if not label:
        raise error(400, "invalid_field", "'label' is required.")

    sign_subtype = clean_str(body.get("sign_subtype"), "sign_subtype", 20)
    custom_id = clean_str(body.get("custom_id"), "custom_id", 20)
    if custom_id:
        existing = tenant_query(Item).filter(
            db.func.upper(Item.custom_id) == custom_id.upper()
        ).first()
        if existing:
            raise error(409, "duplicate_custom_id", f"Custom ID '{custom_id}' is already in use.")
    else:
        custom_id = Item.generate_custom_id(item_type, sign_subtype)

    item = Item(type=item_type, label=label, custom_id=custom_id, status="available")
    item.last_action = "added"
    item.last_action_at = utc_now()
    item.last_action_by_id = g.api_user.id
    _apply_writable_fields(item, {k: v for k, v in body.items() if k not in ("type", "custom_id", "label")} | {"label": label})

    tenant_add(item)
    log_activity(
        f"{item_type.lower()}_added",
        user=g.api_user,
        target=item,
        summary=f"Added {item_type.lower()} {item.label} via API",
        commit=False,
    )
    tenant_commit()
    return jsonify(item.to_dict()), 201


@api_bp.get("/items/<item_ref>")
@api_tenant_required
def get_item(item_ref: str):
    item = _get_item_or_404(item_ref)
    payload = item.to_dict()
    payload["active_checkouts"] = [
        c.to_dict() for c in tenant_query(ItemCheckout)
        .filter_by(item_id=item.id, is_active=True)
        .order_by(ItemCheckout.checked_out_at.desc())
        .all()
    ]
    return jsonify(payload)


@api_bp.patch("/items/<item_ref>")
@api_tenant_required
def update_item(item_ref: str):
    item = _get_item_or_404(item_ref)
    body = get_json_body()

    if "type" in body and body["type"] != item.type:
        raise error(400, "invalid_field", "An item's type cannot be changed.")
    if "custom_id" in body:
        new_custom = clean_str(body.get("custom_id"), "custom_id", 20)
        if not new_custom:
            raise error(400, "invalid_field", "'custom_id' cannot be blank.")
        clash = tenant_query(Item).filter(
            db.func.upper(Item.custom_id) == new_custom.upper(),
            Item.id != item.id,
        ).first()
        if clash:
            raise error(409, "duplicate_custom_id", f"Custom ID '{new_custom}' is already in use.")
        item.custom_id = new_custom
    if "label" in body:
        label = clean_str(body.get("label"), "label", 120)
        if not label:
            raise error(400, "invalid_field", "'label' cannot be blank.")

    _apply_writable_fields(item, body)
    item.last_action_by_id = g.api_user.id

    log_activity(
        f"{item.type.lower()}_updated",
        user=g.api_user,
        target=item,
        summary=f"Updated {item.type.lower()} {item.label} via API",
        meta={"fields": sorted(set(body.keys()))},
        commit=False,
    )
    tenant_commit()
    return jsonify(item.to_dict())


@api_bp.delete("/items/<item_ref>")
@api_tenant_required
def delete_item(item_ref: str):
    require_admin()
    item = _get_item_or_404(item_ref)

    if item.status in ("checked_out", "assigned"):
        raise error(409, "item_in_use",
                    f"Item is currently {item.status}. Check it in before deleting.")
    if item.type == "Sign" and item.sign_subtype == "Assembled Unit":
        pieces = tenant_query(Item).filter_by(parent_sign_id=item.id).count()
        if pieces:
            raise error(409, "item_in_use",
                        "Disassemble this sign before deleting — it still has attached pieces.")

    label, item_type, item_id = item.label, item.type, item.id
    session = get_tenant_session()

    # Delete related records first and detach references — mirrors the web
    # delete flows (existing tenant databases may lack CASCADE on these FKs).
    from utilities.database import AuditItem
    for checkout in tenant_query(ItemCheckout).filter_by(item_id=item_id).all():
        session.delete(checkout)
    for audit_item in tenant_query(AuditItem).filter_by(item_id=item_id).all():
        session.delete(audit_item)
    for child in tenant_query(Item).filter_by(master_key_id=item_id).all():
        child.master_key_id = None
    for piece in tenant_query(Item).filter_by(parent_sign_id=item_id).all():
        piece.parent_sign_id = None
        piece.status = "available"

    session.delete(item)
    log_activity(
        f"{item_type.lower()}_deleted",
        user=g.api_user,
        target_type="Item",
        target_id=item_id,
        summary=f"Deleted {item_type.lower()} {label} via API",
        commit=False,
    )
    tenant_commit()
    return jsonify({"deleted": True, "id": item_id})


# --- Actions ------------------------------------------------------------------

@api_bp.post("/items/<item_ref>/checkout")
@api_tenant_required
def checkout_item(item_ref: str):
    item = _get_item_or_404(item_ref)
    body = get_json_body()
    user = g.api_user

    if item.type == "Key":
        copies = clean_int(body.get("copies"), "copies") or 1
        available = (item.total_copies or 0) - (item.copies_checked_out or 0)
        if copies < 1 or copies > available:
            raise error(409, "no_copies_available",
                        f"Invalid number of copies. Available: {available}.")

        purpose = clean_str(body.get("purpose"), "purpose", 255)
        checked_out_to = clean_str(body.get("checked_out_to"), "checked_out_to", 255) or user.name
        contact_id = _validate_contact_id(body.get("contact_id"))
        expected_return = parse_date(body.get("expected_return_date"), "expected_return_date")

        item.copies_checked_out = (item.copies_checked_out or 0) + copies
        item.status = "checked_out"
        item.checkout_purpose = purpose or item.checkout_purpose
        item.expected_return_date = expected_return or item.expected_return_date
        item.record_action("checked_out", user)

        record = ItemCheckout(
            item_id=item.id,
            checked_out_to=checked_out_to,
            contact_id=contact_id,
            checked_out_by_id=user.id,
            quantity=copies,
            purpose=purpose,
            expected_return_date=expected_return,
            checked_out_at=utc_now(),
            is_active=True,
        )
        tenant_add(record)
        log_activity(
            "key_checked_out",
            user=user,
            target=item,
            summary=f"Checked out {copies} cop{'y' if copies == 1 else 'ies'} of key {item.label} to {checked_out_to}",
            meta={"copies": copies, "checked_out_to": checked_out_to, "purpose": purpose, "via": "api"},
            commit=False,
        )
        tenant_commit()
        _safe_notify_checkout(record)
        return jsonify({"item": item.to_dict(), "checkout": record.to_dict()}), 201

    if item.type == "Lockbox":
        code = clean_str(body.get("code"), "code", 20)
        if not code:
            raise error(400, "invalid_field", "'code' is required to check out a lockbox (rotates the stored code).")

        item.code_previous = item.code_current
        item.code_current = code
        item.status = "checked_out"
        item.record_action("checked_out", user)
        assigned_to = clean_str(body.get("assigned_to"), "assigned_to", 120)
        if assigned_to:
            item.assigned_to = assigned_to
        _apply_optional_location_address(item, body)

        log_activity(
            "lockbox_checked_out",
            user=user,
            target=item,
            summary=f"Checked out lockbox {item.label}",
            meta={"assigned_to": item.assigned_to, "location": item.location, "address": item.address, "via": "api"},
            commit=False,
        )
        tenant_commit()
        return jsonify({"item": item.to_dict()}), 200

    # Sign
    if item.parent_sign_id is not None:
        raise error(409, "item_in_use", "Cannot check out a piece that's part of an assembled unit.")

    item.status = "checked_out"
    item.checkout_purpose = clean_str(body.get("purpose"), "purpose", 255)
    assigned_to = clean_str(body.get("assigned_to"), "assigned_to", 120)
    if assigned_to:
        item.assigned_to = assigned_to
    item.record_action("checked_out", user)
    _apply_optional_location_address(item, body)

    log_activity(
        "sign_checked_out",
        user=user,
        target=item,
        summary=f"Checked out sign {item.label}",
        meta={"assigned_to": item.assigned_to, "location": item.location, "address": item.address, "via": "api"},
        commit=False,
    )
    tenant_commit()
    return jsonify({"item": item.to_dict()}), 200


@api_bp.post("/items/<item_ref>/checkin")
@api_tenant_required
def checkin_item(item_ref: str):
    item = _get_item_or_404(item_ref)
    body = get_json_body()
    user = g.api_user

    if item.type == "Key":
        checkout = None
        checkout_id = clean_int(body.get("checkout_id"), "checkout_id")
        if checkout_id is not None:
            checkout = tenant_query(ItemCheckout).filter_by(
                id=checkout_id, item_id=item.id, is_active=True
            ).first()
            if checkout is None:
                raise error(404, "not_found", f"Active checkout {checkout_id} not found for this key.")
            copies = checkout.quantity
            checked_out_to = checkout.checked_out_to
            checkout.is_active = False
            checkout.checked_in_at = utc_now()
            checkout.checked_in_by_id = user.id
        else:
            copies = clean_int(body.get("copies"), "copies")
            if copies is not None:
                checked_out = item.copies_checked_out or 0
                if copies < 1 or copies > checked_out:
                    raise error(409, "invalid_quantity",
                                f"Invalid number of copies. Checked out: {checked_out}.")
                checked_out_to = "Unknown"
            elif item.status == "assigned" and item.assigned_to:
                copies = item.copies_checked_out or item.total_copies or 1
                checked_out_to = item.assigned_to
            else:
                raise error(400, "invalid_field",
                            "Provide 'checkout_id' or 'copies' to check in this key.")

        item.copies_checked_out = max(0, (item.copies_checked_out or 0) - copies)
        if item.copies_checked_out == 0:
            item.status = "available"
            item.assigned_to = None
            item.assignment_type = None
            item.checkout_purpose = None
            item.expected_return_date = None
        item.record_action("checked_in", user)

        log_activity(
            "key_checked_in",
            user=user,
            target=item,
            summary=f"Checked in {copies} cop{'y' if copies == 1 else 'ies'} of key {item.label} from {checked_out_to}",
            meta={"copies": copies, "checked_out_to": checked_out_to,
                  "checkout_id": checkout_id, "via": "api"},
            commit=False,
        )
        tenant_commit()
        if checkout is not None:
            _safe_notify_checkin(checkout)
        return jsonify({"item": item.to_dict()})

    if item.type == "Lockbox":
        code = clean_str(body.get("code"), "code", 20)
        if not code:
            raise error(400, "invalid_field", "'code' is required to check in a lockbox (rotates the stored code).")

        item.code_previous = item.code_current
        item.code_current = code
        item.status = "available"
        item.assigned_to = None
        item.record_action("checked_in", user)
        _apply_optional_location_address(item, body)

        log_activity(
            "lockbox_checked_in",
            user=user,
            target=item,
            summary=f"Checked in lockbox {item.label}",
            meta={"location": item.location, "address": item.address, "via": "api"},
            commit=False,
        )
        tenant_commit()
        return jsonify({"item": item.to_dict()})

    # Sign
    item.status = "available"
    item.record_action("checked_in", user)
    _apply_optional_location_address(item, body)

    log_activity(
        "sign_checked_in",
        user=user,
        target=item,
        summary=f"Checked in sign {item.label}",
        meta={"location": item.location, "address": item.address, "via": "api"},
        commit=False,
    )
    tenant_commit()
    return jsonify({"item": item.to_dict()})


@api_bp.post("/items/<item_ref>/assign")
@api_tenant_required
def assign_item(item_ref: str):
    item = _get_item_or_404(item_ref)
    body = get_json_body()
    user = g.api_user

    assigned_to = clean_str(body.get("assigned_to"), "assigned_to", 255)
    assignment_type = clean_str(body.get("assignment_type"), "assignment_type", 50)
    expected_return = parse_date(body.get("expected_return_date"), "expected_return_date")
    property_obj, unit_obj = _resolve_property_refs(body)

    if assignment_type == "contractor" and expected_return is None:
        raise error(400, "invalid_field", "Expected return date is required for contractor assignments.")

    if assignment_type == "property":
        if property_obj is None:
            raise error(400, "invalid_field", "Select a property ('property_id') for a property assignment.")
        if not assigned_to:
            if unit_obj:
                assigned_to = f"{property_obj.name} ({unit_obj.label})"
            else:
                assigned_to = property_obj.name
    elif not assigned_to:
        raise error(400, "invalid_field", "'assigned_to' is required.")

    if item.type == "Key":
        if not assignment_type:
            raise error(400, "invalid_field", "'assignment_type' is required for keys (tenant|contractor|property).")
        copies = clean_int(body.get("copies"), "copies") or 1
        available = (item.total_copies or 0) - (item.copies_checked_out or 0)
        if copies < 1 or copies > available:
            raise error(409, "no_copies_available",
                        f"Invalid number of copies. Available: {available}.")

        if property_obj:
            item.property = property_obj
            if not item.address and property_obj.address_line1:
                parts = [property_obj.address_line1, property_obj.city, property_obj.state, property_obj.postal_code]
                item.address = ", ".join([p for p in parts if p])
        if unit_obj:
            item.property_unit = unit_obj

        item.copies_checked_out = (item.copies_checked_out or 0) + copies
        item.status = "assigned"
        item.assigned_to = assigned_to
        item.assignment_type = assignment_type
        item.expected_return_date = expected_return or item.expected_return_date
        item.record_action("assigned", user)

        record = ItemCheckout(
            item_id=item.id,
            checked_out_to=assigned_to,
            contact_id=_validate_contact_id(body.get("contact_id")),
            checked_out_by_id=user.id,
            quantity=copies,
            assignment_type=assignment_type,
            expected_return_date=expected_return,
            address=item.address,
            checked_out_at=utc_now(),
            is_active=True,
        )
        tenant_add(record)
        log_activity(
            "key_assigned",
            user=user,
            target=item,
            summary=f"Assigned {copies} cop{'y' if copies == 1 else 'ies'} of key {item.label} to {assigned_to}",
            meta={"copies": copies, "assigned_to": assigned_to, "assignment_type": assignment_type, "via": "api"},
            commit=False,
        )
        tenant_commit()
        _safe_notify_checkout(record)
        return jsonify({"item": item.to_dict(), "checkout": record.to_dict()}), 201

    if item.type == "Lockbox":
        if property_obj:
            item.property = property_obj
            address = clean_str(body.get("address"), "address", 255)
            if not address:
                parts = [property_obj.address_line1, property_obj.city, property_obj.state, property_obj.postal_code]
                item.address = ", ".join([p for p in parts if p])
        if unit_obj:
            item.property_unit = unit_obj

        item.assigned_to = assigned_to
        item.assignment_type = assignment_type
        item.expected_return_date = expected_return
        item.status = "assigned"
        item.record_action("assigned", user)
        _apply_optional_location_address(item, body)

        log_activity(
            "lockbox_assigned",
            user=user,
            target=item,
            summary=f"Assigned lockbox {item.label} to {assigned_to} ({assignment_type or 'unknown'})",
            meta={"assigned_to": assigned_to, "assignment_type": assignment_type, "via": "api"},
            commit=False,
        )
        tenant_commit()
        return jsonify({"item": item.to_dict()})

    # Sign
    item.status = "assigned"
    item.assigned_to = assigned_to
    item.assignment_type = assignment_type
    item.expected_return_date = expected_return
    item.record_action("assigned", user)
    _apply_optional_location_address(item, body)

    log_activity(
        "sign_assigned",
        user=user,
        target=item,
        summary=f"Assigned sign {item.label} to {assigned_to}",
        meta={"assigned_to": assigned_to, "assignment_type": assignment_type, "via": "api"},
        commit=False,
    )
    tenant_commit()
    return jsonify({"item": item.to_dict()})


# --- Small shared bits ---------------------------------------------------------

def _apply_optional_location_address(item: Item, body: dict):
    if "location" in body:
        item.location = clean_str(body.get("location"), "location", 120)
    if "address" in body:
        item.address = clean_str(body.get("address"), "address", 255)


def _safe_notify_checkout(record: ItemCheckout):
    try:
        from utilities.email import notify_checkout
        notify_checkout(record)
    except Exception:
        pass  # notifications are fire-and-forget; never fail the API call


def _safe_notify_checkin(record: ItemCheckout):
    try:
        from utilities.email import notify_checkin
        notify_checkin(record)
    except Exception:
        pass
