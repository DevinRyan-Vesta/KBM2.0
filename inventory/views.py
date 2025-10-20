# inventory/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from typing import Optional
from utilities.database import (
    db,
    Item,
    ItemCheckout,
    ActivityLog,
    log_activity,
    utc_now,
    Property,
    PropertyUnit,
)

inventory_bp = Blueprint("inventory", __name__, template_folder="../templates")
LOCKBOX_STATUS_OPTIONS = ["available", "assigned", "checked_out", "maintenance", "retired"]
KEY_STATUS_OPTIONS = ["available", "assigned", "checked_out"]
SIGN_STATUS_OPTIONS = ["available", "assigned", "checked_out", "maintenance", "retired"]
SIGN_PIECE_TYPES = ["Frame", "Sign", "Name Rider", "Status Rider", "Bonus Rider"]
SIGN_CONDITION_OPTIONS = ["Excellent", "Good", "Fair", "Poor", "Needs Repair"]

# --- Helpers ---
def _is_lockbox(i: Item) -> bool:
    return i.type.lower() == "lockbox"

def _require_admin():
    if getattr(current_user, "role", "").lower() != "admin":
        abort(403)


def _get_item_or_404(item_id: int) -> Item:
    item = db.session.get(Item, item_id)
    if item is None:
        abort(404)
    return item

def _apply_optional_location_and_address(item: Item, location_raw: Optional[str], address_raw: Optional[str]):
    if location_raw is not None:
        location_clean = location_raw.strip()
        item.location = location_clean or None
    if address_raw is not None:
        address_clean = address_raw.strip()
        item.address = address_clean or None

def _get_redirect_url(default_url: str) -> str:
    """Get redirect URL from request, defaulting to provided URL"""
    next_url = request.form.get('next') or request.args.get('next')
    if next_url:
        return next_url
    return default_url

# --- List + search + bulk (only search wired now) ---
@inventory_bp.route("/lockboxes", methods=["GET"])
@login_required
def list_lockboxes():
    q = (request.args.get("q") or "").strip()
    query = Item.query.filter(Item.type == "Lockbox")

    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Item.custom_id.ilike(like),
                Item.label.ilike(like),
                Item.location.ilike(like),
                Item.address.ilike(like),
                Item.code_current.ilike(like),
                Item.code_previous.ilike(like),
                Item.assigned_to.ilike(like),
            )
        )

    lockboxes = query.order_by(Item.id.desc()).all()
    dynamic_statuses = {(lb.status or "").lower() for lb in lockboxes if lb.status}
    status_choices = sorted(set(LOCKBOX_STATUS_OPTIONS).union(dynamic_statuses))

    properties = Property.query.order_by(Property.name.asc()).all()

    def _property_display(prop: Property) -> str:
        address_bits = [prop.address_line1, prop.city, prop.state]
        address = ", ".join([bit for bit in address_bits if bit])
        return f"{prop.name} - {address}" if address else prop.name

    property_select_options = [["", "-- Select Property --"]]
    property_map = {}
    for prop in properties:
        display = _property_display(prop)
        property_select_options.append([str(prop.id), display])
        property_map[str(prop.id)] = {
            "id": str(prop.id),
            "name": prop.name,
            "display": display,
            "address": {
                "line1": prop.address_line1,
                "city": prop.city,
                "state": prop.state,
                "postal_code": prop.postal_code,
            },
        }

    return render_template(
        "lockboxes.html",
        lockboxes=lockboxes,
        q=q,
        status_options=status_choices,
        property_select_options=property_select_options,
        property_map=property_map,
    )

# --- Add (separate screen) ---
@inventory_bp.route("/lockboxes/new", methods=["GET", "POST"])
@login_required
def add_lockbox():
    properties = Property.query.order_by(Property.name.asc()).all()

    def _property_display(prop: Property) -> str:
        address_bits = [prop.address_line1, prop.city, prop.state]
        address = ", ".join([bit for bit in address_bits if bit])
        return f"{prop.name} - {address}" if address else prop.name

    property_choices: list[dict[str, str]] = []
    property_lookup: dict[str, dict[str, str | None]] = {}
    for prop in properties:
        entry = {
            "id": str(prop.id),
            "display": _property_display(prop),
            "address_line1": prop.address_line1,
            "city": prop.city,
            "state": prop.state,
            "postal_code": prop.postal_code,
        }
        property_choices.append(entry)
        property_lookup[entry["id"]] = entry

    if request.method == "POST":
        label = (request.form.get("label") or "").strip()
        location = (request.form.get("location") or "").strip()
        address = (request.form.get("address") or "").strip()
        # Accept both legacy `code_current` and template `code`
        code = (
            request.form.get("code")
            or request.form.get("code_current")
            or ""
        ).strip()

        if not code:
            flash("Initial code is required.", "error")
            return redirect(url_for("inventory.add_lockbox"))

        if not label:
            flash("Label is required.", "error")
            return redirect(url_for("inventory.add_lockbox"))

        property_id_str = (request.form.get("property_id") or "").strip()
        property_obj = None
        if property_id_str:
            try:
                property_obj = db.session.get(Property, int(property_id_str))
            except ValueError:
                property_obj = None
            if property_obj is None:
                flash("Selected property could not be found.", "error")
                return redirect(url_for("inventory.add_lockbox"))
            if not address:
                address_parts = [
                    property_obj.address_line1,
                    property_obj.city,
                    property_obj.state,
                    property_obj.postal_code,
                ]
                address = ", ".join([part for part in address_parts if part])

        # Generate custom ID
        custom_id = Item.generate_custom_id("Lockbox")

        item = Item(
            type="Lockbox",
            custom_id=custom_id,
            label=label,
            location=location or None,
            address=address or None,
            code_current=code or None,
            code_previous=None,
            status="available",
            last_action="created",
            last_action_at=utc_now(),
            last_action_by_id=getattr(current_user, "id", None),
        )
        db.session.add(item)

        if property_obj:
            item.property = property_obj

        db.session.flush()
        log_activity(
            "lockbox_created",
            user=current_user,
            target=item,
            summary=f"Created lockbox {label}",
            meta={
                "label": label,
                "location": location or None,
                "address": item.address,
                "code": code,
                "property_id": property_obj.id if property_obj else None,
            },
            commit=False,
        )
        db.session.commit()
        flash("Lockbox added.", "success")
        return redirect(url_for("inventory.list_lockboxes"))

    return render_template(
        "lockbox_add.html",
        properties=property_choices,
        property_lookup=property_lookup,
    )

# --- Quick check out (requires entering current code) ---
@inventory_bp.route("/lockboxes/<int:item_id>/checkout", methods=["POST"])
@login_required
def checkout_lockbox(item_id):
    default_redirect = url_for("inventory.list_lockboxes")
    item = _get_item_or_404(item_id)
    if not _is_lockbox(item):
        flash("Not a lockbox.", "error")
        return redirect(_get_redirect_url(default_redirect))

    # Require code input (keeps code_current up to date)
    code = (request.form.get("code") or "").strip()
    if not code:
        flash("Enter the current code to check out.", "error")
        return redirect(_get_redirect_url(default_redirect))

    previous_assigned = item.assigned_to

    # rotate codes
    item.code_previous = item.code_current
    item.code_current = code
    item.status = "checked_out"
    item.last_action = "checked_out"
    item.last_action_at = utc_now()
    item.last_action_by_id = getattr(current_user, "id", None)

    # (optional) assigned_to field free-text now
    assigned_to = request.form.get("assigned_to")
    if assigned_to is not None:
        assigned_to = assigned_to.strip()
        item.assigned_to = assigned_to or item.assigned_to

    _apply_optional_location_and_address(
        item,
        request.form.get("location"),
        request.form.get("address"),
    )

    log_activity(
        "lockbox_checked_out",
        user=current_user,
        target=item,
        summary=f"Checked out lockbox {item.label}",
        meta={
            "code_previous": item.code_previous,
            "code_current": item.code_current,
            "previous_assigned_to": previous_assigned,
            "assigned_to": item.assigned_to,
            "location": item.location,
            "address": item.address,
        },
        commit=False,
    )

    db.session.commit()
    flash("Lockbox checked out.", "success")
    return redirect(_get_redirect_url(default_redirect))

# --- Quick check in (requires entering current code) ---
@inventory_bp.route("/lockboxes/<int:item_id>/checkin", methods=["POST"])
@login_required
def checkin_lockbox(item_id):
    default_redirect = url_for("inventory.list_lockboxes")
    item = _get_item_or_404(item_id)
    if not _is_lockbox(item):
        flash("Not a lockbox.", "error")
        return redirect(_get_redirect_url(default_redirect))

    code = (request.form.get("code") or "").strip()
    if not code:
        flash("Enter the current code to check in.", "error")
        return redirect(_get_redirect_url(default_redirect))

    previous_assigned = item.assigned_to
    item.code_previous = item.code_current
    item.code_current = code
    item.status = "available"
    item.last_action = "checked_in"
    item.last_action_at = utc_now()
    item.last_action_by_id = getattr(current_user, "id", None)

    _apply_optional_location_and_address(
        item,
        request.form.get("location"),
        request.form.get("address"),
    )

    # Clear assignment on check-in (optional)
    item.assigned_to = None

    log_activity(
        "lockbox_checked_in",
        user=current_user,
        target=item,
        summary=f"Checked in lockbox {item.label}",
        meta={
            "code_previous": item.code_previous,
            "code_current": item.code_current,
            "previous_assigned_to": previous_assigned,
            "assigned_to": item.assigned_to,
            "location": item.location,
            "address": item.address,
        },
        commit=False,
    )

    db.session.commit()
    flash("Lockbox checked in.", "success")
    return redirect(_get_redirect_url(default_redirect))

@inventory_bp.post("/lockboxes/bulk")
@login_required
def bulk_lockboxes():
    """Handle bulk actions from the lockboxes list (placeholder)."""
    action = (request.form.get("action") or "").strip().lower()
    id_strings = request.form.getlist("ids")  # checkbox name is `ids`
    try:
        ids = [int(x) for x in id_strings if str(x).isdigit()]
    except ValueError:
        ids = []

    if not ids:
        flash("No lockboxes selected.", "error")
        return redirect(url_for("inventory.list_lockboxes"))

    # Fetch selected lockboxes
    boxes = Item.query.filter(
        Item.type == "Lockbox",
        Item.id.in_(ids)
    ).all()

    if not boxes:
        flash("Selected lockboxes not found.", "error")
        return redirect(url_for("inventory.list_lockboxes"))

    # Placeholder logic – just acknowledge for now.
    if action == "assign":
        flash(f"{len(boxes)} lockbox(es) ready to assign (UI TBD).", "info")
    elif action == "checkout":
        flash(f"{len(boxes)} lockbox(es) ready to check out (UI TBD).", "info")
    elif action == "checkin":
        flash(f"{len(boxes)} lockbox(es) ready to check in (UI TBD).", "info")
    else:
        flash("Unknown action.", "error")

    return redirect(url_for("inventory.list_lockboxes"))

@inventory_bp.post("/lockboxes/<int:item_id>/assign")
@login_required
def assign_lockbox(item_id):
    default_redirect = url_for("inventory.list_lockboxes")
    lb = Item.query.filter_by(id=item_id, type="Lockbox").first()
    if not lb:
        flash("Lockbox not found.", "error")
        return redirect(_get_redirect_url(default_redirect))

    assignee = request.form.get("assignee") or ""
    assignee_clean = assignee.strip()
    assignment_type = (request.form.get("assignment_type") or "").strip()
    expected_return_date_str = (request.form.get("expected_return_date") or "").strip()
    address = (request.form.get("address") or "").strip()
    location = (request.form.get("location") or "").strip()
    property_id_str = (request.form.get("property_id") or "").strip()

    property_obj = None
    if property_id_str:
        try:
            property_obj = db.session.get(Property, int(property_id_str))
        except ValueError:
            property_obj = None
        if property_obj is None:
            flash("Selected property could not be found.", "error")
            return redirect(_get_redirect_url(default_redirect))

    # Validate contractor assignments require return date
    if assignment_type == "contractor" and not expected_return_date_str:
        flash("Expected return date is required for contractor assignments.", "error")
        return redirect(_get_redirect_url(default_redirect))

    # Parse expected return date
    expected_return_date = None
    if expected_return_date_str:
        try:
            expected_return_date = datetime.strptime(expected_return_date_str, "%Y-%m-%d")
        except ValueError:
            flash("Invalid date format.", "error")
            return redirect(_get_redirect_url(default_redirect))

    if assignment_type == "property":
        if property_obj is None:
            flash("Select a property for this assignment.", "error")
            return redirect(_get_redirect_url(default_redirect))
        if not assignee_clean:
            assignee_clean = property_obj.name
    else:
        if not assignee_clean:
            flash("Please provide an assignee.", "error")
            return redirect(_get_redirect_url(default_redirect))

    previous_assignee = lb.assigned_to
    lb.assigned_to = assignee_clean
    lb.assignment_type = assignment_type or None
    lb.expected_return_date = expected_return_date

    if property_obj:
        lb.property = property_obj
        if not address:
            address_parts = [property_obj.address_line1, property_obj.city, property_obj.state, property_obj.postal_code]
            address = ", ".join([part for part in address_parts if part])
    elif not property_id_str:
        lb.property = None

    if address:
        lb.address = address
    if location:
        lb.location = location
    lb.property_unit = None  # lockboxes are not tied to units
    lb.status = "assigned"
    lb.last_action = "assigned"
    lb.last_action_at = utc_now()
    lb.last_action_by_id = getattr(current_user, "id", None)
    log_activity(
        "lockbox_assigned",
        user=current_user,
        target=lb,
        summary=f"Assigned lockbox {lb.label} to {assignee_clean} ({assignment_type or 'unknown'})",
        meta={
            "previous_assignee": previous_assignee,
            "assigned_to": assignee_clean,
            "assignment_type": assignment_type,
            "expected_return_date": expected_return_date.isoformat() if expected_return_date else None,
            "address": address,
            "location": location,
            "property_id": property_obj.id if property_obj else None,
        },
        commit=False,
    )
    db.session.commit()
    flash(f"Lockbox {lb.label} assigned to {assignee_clean}.", "success")
    return redirect(_get_redirect_url(default_redirect))

@inventory_bp.post("/lockboxes/<int:item_id>/edit")
@login_required
def edit_lockbox(item_id: int):
    _require_admin()
    lb = Item.query.filter_by(id=item_id, type="Lockbox").first()
    if not lb:
        flash("Lockbox not found.", "error")
        return redirect(url_for("inventory.list_lockboxes"))

    before = {
        "label": lb.label,
        "location": lb.location,
        "address": lb.address,
        "code_current": lb.code_current,
        "code_previous": lb.code_previous,
        "status": lb.status,
        "assigned_to": lb.assigned_to,
        "property_id": lb.property_id,
    }

    form = request.form
    label = (form.get("label") or "").strip()
    if not label:
        flash("Label is required.", "error")
        return redirect(url_for("inventory.list_lockboxes"))

    lb.label = label
    lb.location = (form.get("location") or "").strip() or None
    lb.address = (form.get("address") or "").strip() or None
    lb.code_current = (form.get("code_current") or "").strip() or None
    lb.code_previous = (form.get("code_previous") or "").strip() or None

    status = (form.get("status") or "").strip().lower()
    if status:
        lb.status = status

    # Preserve optional assignment even if blank to allow clearing
    assigned_to = (form.get("assigned_to") or "").strip()
    lb.assigned_to = assigned_to or None

    property_id_str = (form.get("property_id") or "").strip()
    property_obj = None
    if property_id_str:
        try:
            property_obj = db.session.get(Property, int(property_id_str))
        except ValueError:
            property_obj = None
        if property_obj is None:
            flash("Selected property could not be found.", "error")
            return redirect(url_for("inventory.list_lockboxes"))
    if property_obj or property_id_str == "":
        lb.property = property_obj

    lb.record_action("updated", current_user)

    changes = {}
    for key in before:
        after_value = getattr(lb, key)
        if before[key] != after_value:
            changes[key] = {"from": before[key], "to": after_value}

    if changes:
        log_activity(
            "lockbox_updated",
            user=current_user,
            target=lb,
            summary=f"Updated lockbox {lb.label}",
            meta={"changes": changes},
            commit=False,
        )

    db.session.commit()
    flash(f"Lockbox {lb.label} updated.", "success")
    return redirect(url_for("inventory.list_lockboxes"))

@inventory_bp.post("/lockboxes/<int:item_id>/code")
@login_required
def update_lockbox_code(item_id: int):
    lb = Item.query.filter_by(id=item_id, type="Lockbox").first()
    if not lb:
        flash("Lockbox not found.", "error")
        return redirect(url_for("inventory.list_lockboxes"))

    new_code = (request.form.get("code") or "").strip()
    if not new_code:
        flash("Provide a code to update.", "error")
        return redirect(url_for("inventory.list_lockboxes"))

    previous_code = lb.code_current
    lb.code_previous = previous_code
    lb.code_current = new_code

    _apply_optional_location_and_address(
        lb,
        request.form.get("location"),
        request.form.get("address"),
    )

    lb.record_action("code_updated", current_user)
    log_activity(
        "lockbox_code_updated",
        user=current_user,
        target=lb,
        summary=f"Updated code for lockbox {lb.label}",
        meta={
            "previous_code": previous_code,
            "code_current": lb.code_current,
            "location": lb.location,
            "address": lb.address,
        },
        commit=False,
    )
    db.session.commit()
    flash(f"Lockbox {lb.label} code updated.", "success")
    return redirect(url_for("inventory.list_lockboxes"))


@inventory_bp.post("/lockboxes/<int:item_id>/delete")
@login_required
def delete_lockbox(item_id: int):
    role = (getattr(current_user, "role", "") or "").lower()
    if role == "agent":
        abort(403)

    lb = Item.query.filter_by(id=item_id, type="Lockbox").first()
    if not lb:
        flash("Lockbox not found.", "error")
        return redirect(url_for("inventory.list_lockboxes"))

    info = {
        "label": lb.label,
        "location": lb.location,
        "address": lb.address,
        "status": lb.status,
    }

    db.session.delete(lb)
    log_activity(
        "lockbox_deleted",
        user=current_user,
        target_type="Item",
        target_id=item_id,
        summary=f"Removed lockbox {info['label']}",
        meta=info,
        commit=False,
    )
    db.session.commit()
    flash(f"Lockbox {info['label']} removed.", "success")
    return redirect(url_for("inventory.list_lockboxes"))


# ==================== KEY MANAGEMENT ROUTES ====================

@inventory_bp.route("/keys", methods=["GET"])
@login_required
def list_keys():
    q = (request.args.get("q") or "").strip()
    query = Item.query.filter(Item.type == "Key")

    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Item.custom_id.ilike(like),
                Item.label.ilike(like),
                Item.location.ilike(like),
                Item.address.ilike(like),
                Item.key_hook_number.ilike(like),
                Item.assigned_to.ilike(like),
            )
        )

    keys = query.order_by(Item.id.desc()).all()
    dynamic_statuses = {(k.status or "").lower() for k in keys if k.status}
    status_choices = sorted(set(KEY_STATUS_OPTIONS).union(dynamic_statuses))

    properties = Property.query.order_by(Property.name.asc()).all()
    property_units_map: dict[str, list[dict[str, str]]] = {}

    def _property_display(prop: Property) -> str:
        address_bits = [prop.address_line1, prop.city, prop.state]
        address = ", ".join([bit for bit in address_bits if bit])
        return f"{prop.name} - {address}" if address else prop.name

    property_select_options = [["", "-- Select Property --"]]
    property_map = {}
    for prop in properties:
        display = _property_display(prop)
        property_select_options.append([str(prop.id), display])
        property_map[str(prop.id)] = {
            "id": str(prop.id),
            "name": prop.name,
            "display": display,
            "address": {
                "line1": prop.address_line1,
                "city": prop.city,
                "state": prop.state,
                "postal_code": prop.postal_code,
            },
        }
        property_units_map[str(prop.id)] = [
            {"id": str(unit.id), "label": unit.label}
            for unit in sorted(prop.units, key=lambda u: (u.label or "").lower())
        ]

    # Include orphan units (in case of FK mismatch) - defensive
    extra_units = (
        PropertyUnit.query.filter(PropertyUnit.property_id.is_(None))
        .order_by(PropertyUnit.label.asc())
        .all()
    )
    if extra_units:
        property_units_map.setdefault("", [])
        property_units_map[""].extend([{"id": str(unit.id), "label": unit.label} for unit in extra_units])

    return render_template(
        "keys.html",
        keys=keys,
        q=q,
        status_options=status_choices,
        property_select_options=property_select_options,
        property_map=property_map,
        property_units_map=property_units_map,
    )


@inventory_bp.route("/keys/new", methods=["GET", "POST"])
@login_required
def add_key():
    properties = Property.query.order_by(Property.name.asc()).all()

    def _property_display(prop: Property) -> str:
        address_bits = [prop.address_line1, prop.city, prop.state]
        address = ", ".join([bit for bit in address_bits if bit])
        return f"{prop.name} - {address}" if address else prop.name

    property_choices = []
    property_lookup = {}
    property_units_map: dict[str, list[dict[str, str]]] = {}
    for prop in properties:
        units = [
            {"id": str(unit.id), "label": unit.label}
            for unit in sorted(prop.units, key=lambda u: (u.label or "").lower())
        ]
        entry = {
            "id": str(prop.id),
            "display": _property_display(prop),
            "address_line1": prop.address_line1,
            "city": prop.city,
            "state": prop.state,
            "postal_code": prop.postal_code,
            "units": units,
        }
        property_choices.append(entry)
        property_lookup[entry["id"]] = entry
        property_units_map[entry["id"]] = units

    if request.method == "POST":
        label = (request.form.get("label") or "").strip()
        location = (request.form.get("location") or "").strip()
        address = (request.form.get("address") or "").strip()
        key_hook_number = (request.form.get("key_hook_number") or "").strip()
        keycode = (request.form.get("keycode") or "").strip()
        total_copies_str = (request.form.get("total_copies") or "0").strip()
        property_id_str = (request.form.get("property_id") or "").strip()
        property_unit_id_str = (request.form.get("property_unit_id") or "").strip()

        if not label:
            flash("Label is required.", "error")
            return redirect(url_for("inventory.add_key"))

        try:
            total_copies = int(total_copies_str)
        except ValueError:
            total_copies = 0

        # Generate custom ID
        custom_id = Item.generate_custom_id("Key")

        property_obj = None
        if property_id_str:
            try:
                property_obj = db.session.get(Property, int(property_id_str))
            except ValueError:
                property_obj = None
            if property_obj is None:
                flash("Selected property could not be found.", "error")
                return redirect(url_for("inventory.add_key"))
            if not address:
                address_parts = [property_obj.address_line1, property_obj.city, property_obj.state, property_obj.postal_code]
                address = ", ".join([part for part in address_parts if part])

        property_unit_obj = None
        if property_unit_id_str:
            try:
                property_unit_obj = db.session.get(PropertyUnit, int(property_unit_id_str))
            except ValueError:
                property_unit_obj = None
            if property_unit_obj is None:
                flash("Selected property unit could not be found.", "error")
                return redirect(url_for("inventory.add_key"))
            if property_obj and property_unit_obj.property_id and property_unit_obj.property_id != property_obj.id:
                flash("Selected unit does not belong to the chosen property.", "error")
                return redirect(url_for("inventory.add_key"))
            if property_obj is None:
                property_obj = property_unit_obj.property

        item = Item(
            type="Key",
            custom_id=custom_id,
            label=label,
            location=location or None,
            address=address or None,
            key_hook_number=key_hook_number or None,
            keycode=keycode or None,
            total_copies=total_copies,
            copies_checked_out=0,
            status="available",
            last_action="created",
            last_action_at=utc_now(),
            last_action_by_id=getattr(current_user, "id", None),
            property=property_obj,
            property_unit=property_unit_obj,
        )
        db.session.add(item)
        db.session.flush()
        log_activity(
            "key_created",
            user=current_user,
            target=item,
            summary=f"Created key {label}",
            meta={
                "label": label,
                "location": location or None,
                "address": address or None,
                "total_copies": total_copies,
                "property_id": property_obj.id if property_obj else None,
                "property_unit_id": property_unit_obj.id if property_unit_obj else None,
            },
            commit=False,
        )
        db.session.commit()
        flash("Key added.", "success")
        return redirect(url_for("inventory.list_keys"))

    return render_template(
        "key_add.html",
        properties=property_choices,
        property_lookup=property_lookup,
        property_units_map=property_units_map,
    )


@inventory_bp.route("/keys/<int:item_id>/checkout", methods=["POST"])
@login_required
def checkout_key(item_id):
    default_redirect = url_for("inventory.list_keys")
    key = Item.query.filter_by(id=item_id, type="Key").first()
    if not key:
        flash("Key not found.", "error")
        return redirect(_get_redirect_url(default_redirect))

    copies_str = (request.form.get("copies") or "0").strip()
    try:
        copies = int(copies_str)
    except ValueError:
        copies = 0

    available = (key.total_copies or 0) - (key.copies_checked_out or 0)
    if copies < 1 or copies > available:
        flash(f"Invalid number of copies. Available: {available}", "error")
        return redirect(_get_redirect_url(default_redirect))

    purpose = (request.form.get("purpose") or "").strip()
    checked_out_to = (request.form.get("checked_out_to") or "").strip()
    expected_return_str = (request.form.get("expected_return_date") or "").strip()
    expected_return_date = None
    if expected_return_str:
        try:
            expected_return_date = datetime.strptime(expected_return_str, "%Y-%m-%d")
        except ValueError:
            pass

    # If no name provided, use current user's name
    if not checked_out_to:
        checked_out_to = current_user.name if current_user.is_authenticated else "Unknown"

    key.copies_checked_out = (key.copies_checked_out or 0) + copies
    key.status = "checked_out"
    key.checkout_purpose = purpose or key.checkout_purpose
    key.expected_return_date = expected_return_date or key.expected_return_date
    key.last_action = "checked_out"
    key.last_action_at = utc_now()
    key.last_action_by_id = getattr(current_user, "id", None)

    # Create ItemCheckout record to track who has what
    checkout_record = ItemCheckout(
        item_id=key.id,
        checked_out_to=checked_out_to,
        checked_out_by_id=getattr(current_user, "id", None),
        quantity=copies,
        purpose=purpose or None,
        expected_return_date=expected_return_date,
        checked_out_at=utc_now(),
        is_active=True
    )
    db.session.add(checkout_record)

    log_activity(
        "key_checked_out",
        user=current_user,
        target=key,
        summary=f"Checked out {copies} cop{'y' if copies == 1 else 'ies'} of key {key.label} to {checked_out_to}",
        meta={
            "copies": copies,
            "checked_out_to": checked_out_to,
            "purpose": purpose,
            "expected_return_date": expected_return_str,
        },
        commit=False,
    )

    db.session.commit()
    flash(f"Checked out {copies} cop{'y' if copies == 1 else 'ies'} of key {key.label}.", "success")
    
    # Redirect to receipt page with option to print
    return redirect(url_for('inventory.checkout_receipt', checkout_id=checkout_record.id))


@inventory_bp.route("/keys/<int:item_id>/assign", methods=["POST"])
@login_required
def assign_key(item_id):
    default_redirect = url_for("inventory.list_keys")
    key = Item.query.filter_by(id=item_id, type="Key").first()
    if not key:
        flash("Key not found.", "error")
        return redirect(_get_redirect_url(default_redirect))

    copies_str = (request.form.get("copies") or "0").strip()
    try:
        copies = int(copies_str)
    except ValueError:
        copies = 0

    available = (key.total_copies or 0) - (key.copies_checked_out or 0)
    if copies < 1 or copies > available:
        flash(f"Invalid number of copies. Available: {available}", "error")
        return redirect(_get_redirect_url(default_redirect))

    assigned_to = (request.form.get("assigned_to") or "").strip()
    assignment_type = (request.form.get("assignment_type") or "").strip()
    expected_return_str = (request.form.get("expected_return_date") or "").strip()
    property_id_str = (request.form.get("property_id") or "").strip()
    property_unit_id_str = (request.form.get("property_unit_id") or "").strip()

    property_obj = None
    if property_id_str:
        try:
            property_obj = db.session.get(Property, int(property_id_str))
        except ValueError:
            property_obj = None
        if property_obj is None:
            flash("Selected property could not be found.", "error")
            return redirect(_get_redirect_url(default_redirect))
    property_unit_obj = None
    if property_unit_id_str:
        try:
            property_unit_obj = db.session.get(PropertyUnit, int(property_unit_id_str))
        except ValueError:
            property_unit_obj = None
        if property_unit_obj is None:
            flash("Selected property unit could not be found.", "error")
            return redirect(_get_redirect_url(default_redirect))
        if property_obj and property_unit_obj.property_id and property_unit_obj.property_id != property_obj.id:
            flash("Selected unit does not belong to the chosen property.", "error")
            return redirect(_get_redirect_url(default_redirect))
        if property_obj is None:
            property_obj = property_unit_obj.property

    if not assignment_type:
        flash("Please specify assignment type.", "error")
        return redirect(_get_redirect_url(default_redirect))

    expected_return_date = None
    if expected_return_str:
        try:
            expected_return_date = datetime.strptime(expected_return_str, "%Y-%m-%d")
        except ValueError:
            pass

    if assignment_type == "contractor" and not expected_return_date:
        flash("Expected return date is required for contractor assignments.", "error")
        return redirect(_get_redirect_url(default_redirect))

    if assignment_type == "property":
        if property_obj is None:
            flash("Select a property for this assignment.", "error")
            return redirect(_get_redirect_url(default_redirect))
        if property_unit_obj and not assigned_to:
            assigned_to = f"{property_obj.name} ({property_unit_obj.label})"
        elif not assigned_to:
            assigned_to = property_obj.name
    else:
        if not assigned_to:
            flash("Please specify who the key is assigned to.", "error")
            return redirect(_get_redirect_url(default_redirect))

    if property_obj:
        key.property = property_obj
        if not key.address and property_obj.address_line1:
            address_parts = [property_obj.address_line1, property_obj.city, property_obj.state, property_obj.postal_code]
            key.address = ", ".join([part for part in address_parts if part])
    elif not property_id_str:
        key.property = None
    if property_unit_obj:
        key.property_unit = property_unit_obj
    elif not property_unit_id_str:
        key.property_unit = None

    key.copies_checked_out = (key.copies_checked_out or 0) + copies
    key.status = "assigned"
    key.assigned_to = assigned_to
    key.assignment_type = assignment_type
    key.expected_return_date = expected_return_date or key.expected_return_date
    key.last_action = "assigned"
    key.last_action_at = utc_now()
    key.last_action_by_id = getattr(current_user, "id", None)

    # Create ItemCheckout record to track the assignment
    assignment_record = ItemCheckout(
        item_id=key.id,
        checked_out_to=assigned_to,
        checked_out_by_id=getattr(current_user, "id", None),
        quantity=copies,
        assignment_type=assignment_type,
        expected_return_date=expected_return_date,
        address=key.address,
        checked_out_at=utc_now(),
        is_active=True
    )
    db.session.add(assignment_record)

    log_activity(
        "key_assigned",
        user=current_user,
        target=key,
        summary=f"Assigned {copies} cop{'y' if copies == 1 else 'ies'} of key {key.label} to {assigned_to}",
        meta={
            "copies": copies,
            "assigned_to": assigned_to,
            "assignment_type": assignment_type,
            "expected_return_date": expected_return_str,
            "property_id": property_obj.id if property_obj else None,
            "property_unit_id": property_unit_obj.id if property_unit_obj else None,
        },
        commit=False,
    )

    db.session.commit()
    flash(f"Assigned {copies} cop{'y' if copies == 1 else 'ies'} of key {key.label} to {assigned_to}.", "success")
    
    # Redirect to receipt page with option to print
    return redirect(url_for('inventory.checkout_receipt', checkout_id=assignment_record.id))


@inventory_bp.route("/keys/<int:item_id>/checkin", methods=["POST"])
@login_required
def checkin_key(item_id):
    default_redirect = url_for("inventory.list_keys")
    key = Item.query.filter_by(id=item_id, type="Key").first()
    if not key:
        flash("Key not found.", "error")
        return redirect(_get_redirect_url(default_redirect))

    # Check if a specific checkout_id was provided (for returning specific checkouts)
    checkout_id_str = (request.form.get("checkout_id") or "").strip()

    if checkout_id_str:
        # Return a specific checkout
        try:
            checkout_id = int(checkout_id_str)
            checkout = ItemCheckout.query.filter_by(
                id=checkout_id,
                item_id=item_id,
                is_active=True
            ).first()

            if not checkout:
                flash("Checkout record not found.", "error")
                return redirect(_get_redirect_url(default_redirect))

            copies = checkout.quantity
            checked_out_to = checkout.checked_out_to

            # Mark checkout as returned
            checkout.is_active = False
            checkout.checked_in_at = utc_now()
            checkout.checked_in_by_id = getattr(current_user, "id", None)
        except ValueError:
            flash("Invalid checkout ID.", "error")
            return redirect(_get_redirect_url(default_redirect))
    else:
        # Check if copies parameter is provided
        copies_str = (request.form.get("copies") or "").strip()

        if copies_str:
            # Legacy: Return specific number of copies
            try:
                copies = int(copies_str)
            except ValueError:
                copies = 0

            checked_out = key.copies_checked_out or 0
            if copies < 1 or copies > checked_out:
                flash(f"Invalid number of copies. Checked out: {checked_out}", "error")
                return redirect(_get_redirect_url(default_redirect))

            checked_out_to = "Unknown"
        else:
            # No copies specified and no checkout_id - return all copies for assigned keys
            if key.status == "assigned" and key.assigned_to:
                copies = key.copies_checked_out or key.total_copies or 1
                checked_out_to = key.assigned_to
            else:
                flash("Please specify the number of copies to check in.", "error")
                return redirect(_get_redirect_url(default_redirect))

    key.copies_checked_out = max(0, (key.copies_checked_out or 0) - copies)

    # If all copies are back, update status
    if key.copies_checked_out == 0:
        key.status = "available"
        key.assigned_to = None
        key.assignment_type = None
        key.checkout_purpose = None
        key.expected_return_date = None

    key.last_action = "checked_in"
    key.last_action_at = utc_now()
    key.last_action_by_id = getattr(current_user, "id", None)

    log_activity(
        "key_checked_in",
        user=current_user,
        target=key,
        summary=f"Checked in {copies} cop{'y' if copies == 1 else 'ies'} of key {key.label} from {checked_out_to}",
        meta={
            "copies": copies,
            "checked_out_to": checked_out_to,
            "checkout_id": checkout_id_str if checkout_id_str else None,
        },
        commit=False,
    )

    db.session.commit()
    flash(f"Checked in {copies} cop{'y' if copies == 1 else 'ies'} of key {key.label}.", "success")
    return redirect(_get_redirect_url(default_redirect))


@inventory_bp.route("/keys/<int:item_id>/active-checkouts", methods=["GET"])
@login_required
def get_key_active_checkouts(item_id):
    """Return active checkouts for a key as JSON"""
    key = Item.query.filter_by(id=item_id, type="Key").first()
    if not key:
        return jsonify({"error": "Key not found"}), 404

    active_checkouts = ItemCheckout.query.filter_by(
        item_id=item_id,
        is_active=True
    ).order_by(ItemCheckout.checked_out_at.desc()).all()

    checkouts_data = []
    for checkout in active_checkouts:
        checkouts_data.append({
            "id": checkout.id,
            "checked_out_to": checkout.checked_out_to,
            "quantity": checkout.quantity,
            "purpose": checkout.purpose,
            "checked_out_at": checkout.checked_out_at.strftime("%Y-%m-%d %H:%M") if checkout.checked_out_at else None,
            "expected_return_date": checkout.expected_return_date.strftime("%Y-%m-%d") if checkout.expected_return_date else None,
        })

    return jsonify({"checkouts": checkouts_data})


@inventory_bp.route("/keys/<int:item_id>/adjust-quantity", methods=["POST"])
@login_required
def adjust_key_quantity(item_id):
    key = Item.query.filter_by(id=item_id, type="Key").first()
    if not key:
        flash("Key not found.", "error")
        return redirect(url_for("inventory.list_keys"))

    new_total_str = (request.form.get("new_total") or "0").strip()
    try:
        new_total = int(new_total_str)
    except ValueError:
        new_total = 0

    if new_total < 0:
        flash("Total copies cannot be negative.", "error")
        return redirect(url_for("inventory.list_keys"))

    reason = (request.form.get("reason") or "").strip()
    notes = (request.form.get("notes") or "").strip()

    old_total = key.total_copies or 0
    key.total_copies = new_total
    key.last_action = "quantity_adjusted"
    key.last_action_at = utc_now()
    key.last_action_by_id = getattr(current_user, "id", None)

    log_activity(
        "key_quantity_adjusted",
        user=current_user,
        target=key,
        summary=f"Adjusted quantity for key {key.label} from {old_total} to {new_total}",
        meta={
            "old_total": old_total,
            "new_total": new_total,
            "reason": reason,
            "notes": notes,
        },
        commit=False,
    )

    db.session.commit()
    flash(f"Updated quantity for key {key.label} to {new_total} copies.", "success")
    return redirect(url_for("inventory.list_keys"))


@inventory_bp.post("/keys/<int:item_id>/edit")
@login_required
def edit_key(item_id: int):
    _require_admin()
    key = Item.query.filter_by(id=item_id, type="Key").first()
    if not key:
        flash("Key not found.", "error")
        return redirect(url_for("inventory.list_keys"))

    before = {
        "label": key.label,
        "location": key.location,
        "address": key.address,
        "key_hook_number": key.key_hook_number,
        "keycode": key.keycode,
        "total_copies": key.total_copies,
        "status": key.status,
        "assigned_to": key.assigned_to,
        "property_id": key.property_id,
        "property_unit_id": key.property_unit_id,
    }

    form = request.form
    label = (form.get("label") or "").strip()
    if not label:
        flash("Label is required.", "error")
        return redirect(url_for("inventory.list_keys"))

    key.label = label
    key.location = (form.get("location") or "").strip() or None
    key.address = (form.get("address") or "").strip() or None
    key.key_hook_number = (form.get("key_hook_number") or "").strip() or None
    key.keycode = (form.get("keycode") or "").strip() or None

    total_copies_str = (form.get("total_copies") or "0").strip()
    try:
        key.total_copies = int(total_copies_str)
    except ValueError:
        key.total_copies = 0

    status = (form.get("status") or "").strip().lower()
    if status:
        key.status = status

    assigned_to = (form.get("assigned_to") or "").strip()
    key.assigned_to = assigned_to or None

    property_id_str = (form.get("property_id") or "").strip()
    property_unit_id_str = (form.get("property_unit_id") or "").strip()
    property_obj = None
    if property_id_str:
        try:
            property_obj = db.session.get(Property, int(property_id_str))
        except ValueError:
            property_obj = None
        if property_obj is None:
            flash("Selected property could not be found.", "error")
            return redirect(url_for("inventory.list_keys"))

    property_unit_obj = None
    if property_unit_id_str:
        try:
            property_unit_obj = db.session.get(PropertyUnit, int(property_unit_id_str))
        except ValueError:
            property_unit_obj = None
        if property_unit_obj is None:
            flash("Selected property unit could not be found.", "error")
            return redirect(url_for("inventory.list_keys"))
        if property_obj and property_unit_obj.property_id and property_unit_obj.property_id != property_obj.id:
            flash("Selected unit does not belong to the chosen property.", "error")
            return redirect(url_for("inventory.list_keys"))
        if property_obj is None:
            property_obj = property_unit_obj.property

    if property_obj or property_id_str == "":
        key.property = property_obj
    if property_unit_obj or property_unit_id_str == "":
        key.property_unit = property_unit_obj

    key.record_action("updated", current_user)

    changes = {}
    for k in before:
        after_value = getattr(key, k)
        if before[k] != after_value:
            changes[k] = {"from": before[k], "to": after_value}

    if changes:
        log_activity(
            "key_updated",
            user=current_user,
            target=key,
            summary=f"Updated key {key.label}",
            meta={"changes": changes},
            commit=False,
        )

    db.session.commit()
    flash(f"Key {key.label} updated.", "success")
    return redirect(url_for("inventory.list_keys"))


@inventory_bp.post("/keys/<int:item_id>/delete")
@login_required
def delete_key(item_id: int):
    role = (getattr(current_user, "role", "") or "").lower()
    if role == "agent":
        abort(403)

    key = Item.query.filter_by(id=item_id, type="Key").first()
    if not key:
        flash("Key not found.", "error")
        return redirect(url_for("inventory.list_keys"))

    info = {
        "label": key.label,
        "location": key.location,
        "address": key.address,
        "total_copies": key.total_copies,
        "status": key.status,
    }

    db.session.delete(key)
    log_activity(
        "key_deleted",
        user=current_user,
        target_type="Item",
        target_id=item_id,
        summary=f"Removed key {info['label']}",
        meta=info,
        commit=False,
    )
    db.session.commit()
    flash(f"Key {info['label']} removed.", "success")
    return redirect(url_for("inventory.list_keys"))


# ==================== SIGN MANAGEMENT ROUTES ====================

@inventory_bp.route("/signs", methods=["GET"])
@login_required
def list_signs():
    q = (request.args.get("q") or "").strip()
    query = Item.query.filter(Item.type == "Sign")

    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Item.custom_id.ilike(like),
                Item.label.ilike(like),
                Item.location.ilike(like),
                Item.address.ilike(like),
                Item.sign_subtype.ilike(like),
                Item.piece_type.ilike(like),
                Item.rider_text.ilike(like),
                Item.material.ilike(like),
                Item.assigned_to.ilike(like),
            )
        )

    signs = query.order_by(Item.id.desc()).all()
    dynamic_statuses = {(s.status or "").lower() for s in signs if s.status}
    status_choices = sorted(set(SIGN_STATUS_OPTIONS).union(dynamic_statuses))

    # Get available pieces for building assembled units
    available_pieces = Item.query.filter(
        Item.type == "Sign",
        Item.sign_subtype == "Piece",
        Item.parent_sign_id.is_(None),
        Item.status == "available"
    ).all()

    return render_template(
        "signs.html",
        signs=signs,
        q=q,
        status_options=status_choices,
        piece_types=SIGN_PIECE_TYPES,
        condition_options=SIGN_CONDITION_OPTIONS,
        available_pieces=available_pieces,
    )


@inventory_bp.route("/signs/new", methods=["GET", "POST"])
@login_required
def add_sign():
    if request.method == "POST":
        label = (request.form.get("label") or "").strip()
        location = (request.form.get("location") or "").strip()
        address = (request.form.get("address") or "").strip()
        sign_subtype = (request.form.get("sign_subtype") or "").strip()
        piece_type = (request.form.get("piece_type") or "").strip()
        rider_text = (request.form.get("rider_text") or "").strip()
        material = (request.form.get("material") or "").strip()
        condition = (request.form.get("condition") or "").strip()

        if not label:
            flash("Label is required.", "error")
            return redirect(url_for("inventory.add_sign"))

        if not sign_subtype:
            flash("Sign type is required (Piece or Assembled Unit).", "error")
            return redirect(url_for("inventory.add_sign"))

        # Generate custom ID (ASA for assembled units, S for pieces)
        custom_id = Item.generate_custom_id("Sign", sign_subtype=sign_subtype)

        item = Item(
            type="Sign",
            custom_id=custom_id,
            label=label,
            location=location or None,
            address=address or None,
            sign_subtype=sign_subtype,
            piece_type=piece_type or None,
            rider_text=rider_text or None,
            material=material or None,
            condition=condition or None,
            status="available",
            last_action="created",
            last_action_at=utc_now(),
            last_action_by_id=getattr(current_user, "id", None),
        )
        db.session.add(item)
        db.session.flush()
        log_activity(
            "sign_created",
            user=current_user,
            target=item,
            summary=f"Created sign {label}",
            meta={
                "label": label,
                "location": location or None,
                "address": address or None,
                "sign_subtype": sign_subtype,
                "piece_type": piece_type or None,
                "material": material or None,
                "condition": condition or None,
            },
            commit=False,
        )
        db.session.commit()
        flash(f"Sign '{label}' added successfully.", "success")
        return redirect(url_for("inventory.list_signs"))

    return render_template(
        "sign_add.html",
        piece_types=SIGN_PIECE_TYPES,
        condition_options=SIGN_CONDITION_OPTIONS,
    )


@inventory_bp.route("/signs/<int:item_id>/checkout", methods=["POST"])
@login_required
def checkout_sign(item_id):
    default_redirect = url_for("inventory.list_signs")
    sign = Item.query.filter_by(id=item_id, type="Sign").first()
    if not sign:
        flash("Sign not found.", "error")
        return redirect(_get_redirect_url(default_redirect))

    if sign.parent_sign_id is not None:
        flash("Cannot check out a piece that's part of an assembled unit.", "error")
        return redirect(_get_redirect_url(default_redirect))

    purpose = (request.form.get("purpose") or "").strip()
    assigned_to = (request.form.get("assigned_to") or "").strip()

    sign.status = "checked_out"
    sign.checkout_purpose = purpose or None
    sign.assigned_to = assigned_to or sign.assigned_to
    sign.last_action = "checked_out"
    sign.last_action_at = utc_now()
    sign.last_action_by_id = getattr(current_user, "id", None)

    _apply_optional_location_and_address(
        sign,
        request.form.get("location"),
        request.form.get("address"),
    )

    log_activity(
        "sign_checked_out",
        user=current_user,
        target=sign,
        summary=f"Checked out sign {sign.label}",
        meta={
            "purpose": purpose,
            "assigned_to": sign.assigned_to,
            "location": sign.location,
            "address": sign.address,
        },
        commit=False,
    )

    db.session.commit()
    flash(f"Sign '{sign.label}' checked out successfully.", "success")
    return redirect(_get_redirect_url(default_redirect))


@inventory_bp.route("/signs/<int:item_id>/checkin", methods=["POST"])
@login_required
def checkin_sign(item_id):
    default_redirect = url_for("inventory.list_signs")
    sign = Item.query.filter_by(id=item_id, type="Sign").first()
    if not sign:
        flash("Sign not found.", "error")
        return redirect(_get_redirect_url(default_redirect))

    sign.status = "available"
    sign.last_action = "checked_in"
    sign.last_action_at = utc_now()
    sign.last_action_by_id = getattr(current_user, "id", None)

    _apply_optional_location_and_address(
        sign,
        request.form.get("location"),
        request.form.get("address"),
    )

    log_activity(
        "sign_checked_in",
        user=current_user,
        target=sign,
        summary=f"Checked in sign {sign.label}",
        meta={
            "location": sign.location,
            "address": sign.address,
        },
        commit=False,
    )

    db.session.commit()
    flash(f"Sign '{sign.label}' checked in successfully.", "success")
    return redirect(_get_redirect_url(default_redirect))


@inventory_bp.route("/signs/<int:item_id>/assign", methods=["POST"])
@login_required
def assign_sign(item_id):
    default_redirect = url_for("inventory.list_signs")
    sign = Item.query.filter_by(id=item_id, type="Sign").first()
    if not sign:
        flash("Sign not found.", "error")
        return redirect(_get_redirect_url(default_redirect))

    assigned_to = (request.form.get("assigned_to") or "").strip()
    if not assigned_to:
        flash("Assignment target is required.", "error")
        return redirect(_get_redirect_url(default_redirect))

    assignment_type = (request.form.get("assignment_type") or "").strip()
    expected_return_str = (request.form.get("expected_return_date") or "").strip()
    expected_return_date = None
    if expected_return_str:
        try:
            expected_return_date = datetime.strptime(expected_return_str, "%Y-%m-%d")
        except ValueError:
            pass

    previous_assigned = sign.assigned_to
    sign.status = "assigned"
    sign.assigned_to = assigned_to
    sign.assignment_type = assignment_type or None
    sign.expected_return_date = expected_return_date
    sign.last_action = "assigned"
    sign.last_action_at = utc_now()
    sign.last_action_by_id = getattr(current_user, "id", None)

    _apply_optional_location_and_address(
        sign,
        request.form.get("location"),
        request.form.get("address"),
    )

    log_activity(
        "sign_assigned",
        user=current_user,
        target=sign,
        summary=f"Assigned sign {sign.label} to {assigned_to}",
        meta={
            "previous_assigned_to": previous_assigned,
            "assigned_to": assigned_to,
            "assignment_type": assignment_type,
            "expected_return_date": expected_return_str,
            "location": sign.location,
            "address": sign.address,
        },
        commit=False,
    )

    db.session.commit()
    flash(f"Sign '{sign.label}' assigned to {assigned_to}.", "success")
    return redirect(_get_redirect_url(default_redirect))


@inventory_bp.post("/signs/<int:item_id>/edit")
@login_required
def edit_sign(item_id: int):
    _require_admin()
    sign = Item.query.filter_by(id=item_id, type="Sign").first()
    if not sign:
        flash("Sign not found.", "error")
        return redirect(url_for("inventory.list_signs"))

    before = {
        "label": sign.label,
        "location": sign.location,
        "address": sign.address,
        "sign_subtype": sign.sign_subtype,
        "piece_type": sign.piece_type,
        "rider_text": sign.rider_text,
        "material": sign.material,
        "condition": sign.condition,
        "status": sign.status,
        "assigned_to": sign.assigned_to,
    }

    form = request.form
    label = (form.get("label") or "").strip()
    if not label:
        flash("Label is required.", "error")
        return redirect(url_for("inventory.list_signs"))

    sign.label = label
    sign.location = (form.get("location") or "").strip() or None
    sign.address = (form.get("address") or "").strip() or None
    sign.sign_subtype = (form.get("sign_subtype") or "").strip() or None
    sign.piece_type = (form.get("piece_type") or "").strip() or None
    sign.rider_text = (form.get("rider_text") or "").strip() or None
    sign.material = (form.get("material") or "").strip() or None
    sign.condition = (form.get("condition") or "").strip() or None

    status = (form.get("status") or "").strip().lower()
    if status:
        sign.status = status

    assigned_to = (form.get("assigned_to") or "").strip()
    sign.assigned_to = assigned_to or None

    sign.record_action("updated", current_user)

    changes = {}
    for k in before:
        after_value = getattr(sign, k)
        if before[k] != after_value:
            changes[k] = {"from": before[k], "to": after_value}

    if changes:
        log_activity(
            "sign_updated",
            user=current_user,
            target=sign,
            summary=f"Updated sign {sign.label}",
            meta={"changes": changes},
            commit=False,
        )

    db.session.commit()
    flash(f"Sign '{sign.label}' updated successfully.", "success")
    return redirect(url_for("inventory.list_signs"))


@inventory_bp.post("/signs/<int:item_id>/delete")
@login_required
def delete_sign(item_id: int):
    role = (getattr(current_user, "role", "") or "").lower()
    if role == "agent":
        abort(403)

    sign = Item.query.filter_by(id=item_id, type="Sign").first()
    if not sign:
        flash("Sign not found.", "error")
        return redirect(url_for("inventory.list_signs"))

    # Check if this is an assembled unit with pieces
    if sign.sign_subtype == "Assembled Unit":
        pieces = Item.query.filter_by(parent_sign_id=item_id).all()
        if pieces:
            flash("Cannot delete assembled unit with pieces. Disassemble first.", "error")
            return redirect(url_for("inventory.list_signs"))

    info = {
        "label": sign.label,
        "location": sign.location,
        "address": sign.address,
        "sign_subtype": sign.sign_subtype,
        "piece_type": sign.piece_type,
        "status": sign.status,
    }

    db.session.delete(sign)
    log_activity(
        "sign_deleted",
        user=current_user,
        target_type="Item",
        target_id=item_id,
        summary=f"Removed sign {info['label']}",
        meta=info,
        commit=False,
    )
    db.session.commit()
    flash(f"Sign '{info['label']}' removed successfully.", "success")
    return redirect(url_for("inventory.list_signs"))


@inventory_bp.route("/signs/builder", methods=["GET", "POST"])
@login_required
def build_sign():
    """Build an assembled unit from individual pieces"""
    if request.method == "POST":
        label = (request.form.get("label") or "").strip()
        if not label:
            flash("Assembled unit label is required.", "error")
            return redirect(url_for("inventory.build_sign"))

        # Get selected piece IDs
        piece_ids = []
        for piece_type in SIGN_PIECE_TYPES:
            piece_id_str = request.form.get(f"piece_{piece_type.lower().replace(' ', '_')}")
            if piece_id_str:
                try:
                    piece_ids.append(int(piece_id_str))
                except ValueError:
                    pass

        if not piece_ids:
            flash("Select at least one piece to build an assembled unit.", "error")
            return redirect(url_for("inventory.build_sign"))

        # Verify all pieces exist and are available
        pieces = Item.query.filter(
            Item.id.in_(piece_ids),
            Item.type == "Sign",
            Item.sign_subtype == "Piece",
            Item.parent_sign_id.is_(None),
            Item.status == "available"
        ).all()

        if len(pieces) != len(piece_ids):
            flash("Some selected pieces are not available.", "error")
            return redirect(url_for("inventory.build_sign"))

        # Create the assembled unit with ASA prefix
        custom_id = Item.generate_custom_id("Sign", sign_subtype="Assembled Unit")
        assembled_unit = Item(
            type="Sign",
            custom_id=custom_id,
            label=label,
            sign_subtype="Assembled Unit",
            status="available",
            location=(request.form.get("location") or "").strip() or None,
            address=(request.form.get("address") or "").strip() or None,
            material=(request.form.get("material") or "").strip() or None,
            condition=(request.form.get("condition") or "").strip() or None,
            last_action="created",
            last_action_at=utc_now(),
            last_action_by_id=getattr(current_user, "id", None),
        )
        db.session.add(assembled_unit)
        db.session.flush()

        # Link pieces to assembled unit
        piece_labels = []
        for piece in pieces:
            piece.parent_sign_id = assembled_unit.id
            piece.status = "assigned"
            piece_labels.append(f"{piece.piece_type}: {piece.label}")

        log_activity(
            "sign_assembled",
            user=current_user,
            target=assembled_unit,
            summary=f"Built assembled sign '{label}' from {len(pieces)} pieces",
            meta={
                "label": label,
                "piece_ids": piece_ids,
                "pieces": piece_labels,
            },
            commit=False,
        )

        db.session.commit()
        flash(f"Assembled unit '{label}' built successfully from {len(pieces)} pieces.", "success")
        return redirect(url_for("inventory.list_signs"))

    # GET request - show builder form
    available_pieces = Item.query.filter(
        Item.type == "Sign",
        Item.sign_subtype == "Piece",
        Item.parent_sign_id.is_(None),
        Item.status == "available"
    ).all()

    # Group pieces by type
    pieces_by_type = {}
    for piece_type in SIGN_PIECE_TYPES:
        pieces_by_type[piece_type] = [
            p for p in available_pieces if p.piece_type == piece_type
        ]

    return render_template(
        "sign_builder.html",
        pieces_by_type=pieces_by_type,
        piece_types=SIGN_PIECE_TYPES,
        condition_options=SIGN_CONDITION_OPTIONS,
    )


@inventory_bp.post("/signs/<int:item_id>/disassemble")
@login_required
def disassemble_sign(item_id: int):
    """Disassemble an assembled unit back into individual pieces"""
    sign = Item.query.filter_by(id=item_id, type="Sign", sign_subtype="Assembled Unit").first()
    if not sign:
        flash("Assembled unit not found.", "error")
        return redirect(url_for("inventory.list_signs"))

    # Get all pieces belonging to this assembled unit
    pieces = Item.query.filter_by(parent_sign_id=item_id).all()

    if not pieces:
        flash("No pieces found for this assembled unit.", "error")
        return redirect(url_for("inventory.list_signs"))

    # Release all pieces
    piece_labels = []
    for piece in pieces:
        piece.parent_sign_id = None
        piece.status = "available"
        piece_labels.append(f"{piece.piece_type}: {piece.label}")

    # Delete the assembled unit
    unit_label = sign.label
    db.session.delete(sign)

    log_activity(
        "sign_disassembled",
        user=current_user,
        target_type="Item",
        target_id=item_id,
        summary=f"Disassembled sign '{unit_label}' into {len(pieces)} pieces",
        meta={
            "label": unit_label,
            "pieces": piece_labels,
        },
        commit=False,
    )

    db.session.commit()
    flash(f"Assembled unit '{unit_label}' disassembled. {len(pieces)} pieces are now available.", "success")
    return redirect(url_for("inventory.list_signs"))


# ==================== ITEM DETAILS PAGE ====================



@inventory_bp.route("/checkout/<int:checkout_id>/receipt", methods=["GET"])
@login_required
def checkout_receipt(checkout_id):
    """Display checkout receipt for printing"""
    checkout = ItemCheckout.query.filter_by(id=checkout_id).first()
    if not checkout:
        flash("Checkout record not found.", "error")
        return redirect(url_for("main.home"))

    item = checkout.item
    if not item:
        flash("Item not found.", "error")
        return redirect(url_for("main.home"))

    # Generate barcode for receipt ID
    import barcode
    from barcode.writer import SVGWriter
    from io import BytesIO
    import base64

    barcode_data = f"RCP{checkout_id:06d}"  # Format: RCP000001
    code128 = barcode.get('code128', barcode_data, writer=SVGWriter())
    barcode_io = BytesIO()
    code128.write(barcode_io, options={'write_text': False, 'module_height': 10, 'module_width': 0.3})
    barcode_svg = base64.b64encode(barcode_io.getvalue()).decode('utf-8')

    from datetime import datetime
    return render_template(
        "checkout_receipt.html",
        checkout=checkout,
        item=item,
        now=datetime.now(),
        barcode_svg=barcode_svg,
        barcode_data=barcode_data
    )


@inventory_bp.route("/receipts", methods=["GET"])
@login_required
def receipt_lookup():
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
            results = ItemCheckout.query.filter(or_(*filters)).order_by(
                ItemCheckout.checked_out_at.desc()
            ).limit(50).all()
    
    return render_template("receipt_lookup.html", results=results, query=query)

@inventory_bp.route("/items/<int:item_id>", methods=["GET"])
@login_required
def item_details(item_id):
    """Comprehensive details page for any item (Lockbox, Key, or Sign)"""
    item = _get_item_or_404(item_id)

    # Get active checkouts for this item
    active_checkouts = ItemCheckout.query.filter_by(
        item_id=item_id,
        is_active=True
    ).order_by(ItemCheckout.checked_out_at.desc()).all()

    # Get checkout history (returned items)
    checkout_history = ItemCheckout.query.filter_by(
        item_id=item_id,
        is_active=False
    ).order_by(ItemCheckout.checked_in_at.desc()).limit(20).all()

    # Get full activity history
    activity_logs = ActivityLog.query.filter_by(
        target_id=item_id,
        target_type="Item"
    ).order_by(ActivityLog.created_at.desc()).limit(50).all()

    # For assembled signs, get component pieces
    component_pieces = []
    if item.type == "Sign" and item.sign_subtype == "Assembled Unit":
        component_pieces = Item.query.filter_by(parent_sign_id=item_id).all()

    # For sign pieces, get parent assembled unit
    parent_unit = None
    if item.type == "Sign" and item.parent_sign_id:
        parent_unit = db.session.get(Item, item.parent_sign_id)

    # Determine available actions based on item type and status
    status_lower = (item.status or "").lower()
    item_type_lower = (item.type or "").lower()

    # Calculate availability for keys
    available_copies = 0
    if item_type_lower == "key":
        available_copies = (item.total_copies or 0) - (item.copies_checked_out or 0)

    # Determine which actions are available
    can_checkout = False
    can_checkin = False
    can_assign = False

    if item_type_lower == "lockbox":
        can_checkout = status_lower in ["available", "assigned"]
        can_checkin = status_lower == "checked_out"
        can_assign = status_lower == "available"
    elif item_type_lower == "key":
        can_checkout = available_copies > 0
        can_checkin = (item.copies_checked_out or 0) > 0
        can_assign = available_copies > 0
    elif item_type_lower == "sign":
        # Cannot checkout pieces that belong to assembled units
        if item.parent_sign_id is None:
            can_checkout = status_lower in ["available", "assigned"]
            can_checkin = status_lower == "checked_out"
            can_assign = status_lower == "available"

    # Pass appropriate status and piece type options
    status_options = []
    if item_type_lower == "lockbox":
        status_options = LOCKBOX_STATUS_OPTIONS
    elif item_type_lower == "key":
        status_options = KEY_STATUS_OPTIONS
    elif item_type_lower == "sign":
        status_options = SIGN_STATUS_OPTIONS

    property_select_options = []
    property_map = {}
    property_units_map: dict[str, list[dict[str, str]]] = {}
    if item_type_lower in {"lockbox", "key"}:
        properties = Property.query.order_by(Property.name.asc()).all()

        def _property_display(prop: Property) -> str:
            address_bits = [prop.address_line1, prop.city, prop.state]
            address = ", ".join([bit for bit in address_bits if bit])
            return f"{prop.name} - {address}" if address else prop.name

        property_select_options.append(["", "-- Select Property --"])
        for prop in properties:
            display = _property_display(prop)
            property_select_options.append([str(prop.id), display])
            property_map[str(prop.id)] = {
                "id": str(prop.id),
                "name": prop.name,
                "display": display,
                "address": {
                    "line1": prop.address_line1,
                    "city": prop.city,
                    "state": prop.state,
                    "postal_code": prop.postal_code,
                },
            }
            property_units_map[str(prop.id)] = [
                {"id": str(unit.id), "label": unit.label}
                for unit in sorted(prop.units, key=lambda u: (u.label or "").lower())
            ]

        extra_units = (
            PropertyUnit.query.filter(PropertyUnit.property_id.is_(None))
            .order_by(PropertyUnit.label.asc())
            .all()
        )
        if extra_units:
            property_units_map.setdefault("", [])
            property_units_map[""].extend([{"id": str(unit.id), "label": unit.label} for unit in extra_units])

    status_options_lower = [opt.lower() for opt in status_options]

    return render_template(
        "item_details.html",
        item=item,
        active_checkouts=active_checkouts,
        checkout_history=checkout_history,
        activity_logs=activity_logs,
        component_pieces=component_pieces,
        parent_unit=parent_unit,
        available_copies=available_copies,
        can_checkout=can_checkout,
        can_checkin=can_checkin,
        can_assign=can_assign,
        status_options=status_options,
        status_options_lower=status_options_lower,
        piece_types=SIGN_PIECE_TYPES if item_type_lower == "sign" else [],
        condition_options=SIGN_CONDITION_OPTIONS if item_type_lower == "sign" else [],
        property_select_options=property_select_options,
        property_map=property_map,
        property_units_map=property_units_map,
        item_type_lower=item_type_lower,
    )
