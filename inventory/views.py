# inventory/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from datetime import datetime
from typing import Optional
from utilities.database import db, Item, log_activity

inventory_bp = Blueprint("inventory", __name__, template_folder="../templates")
LOCKBOX_STATUS_OPTIONS = ["available", "assigned", "checked_out", "maintenance", "retired"]

# --- Helpers ---
def _is_lockbox(i: Item) -> bool:
    return i.type.lower() == "lockbox"

def _require_admin():
    if getattr(current_user, "role", "").lower() != "admin":
        abort(403)

def _apply_optional_location_and_address(item: Item, location_raw: Optional[str], address_raw: Optional[str]):
    if location_raw is not None:
        location_clean = location_raw.strip()
        item.location = location_clean or None
    if address_raw is not None:
        address_clean = address_raw.strip()
        item.address = address_clean or None

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
                Item.label.ilike(like),
                Item.location.ilike(like),
                Item.address.ilike(like),
                Item.code_current.ilike(like),
                Item.code_previous.ilike(like),
                Item.assigned_to.ilike(like),
                db.cast(Item.id, db.String).ilike(like),
            )
        )

    lockboxes = query.order_by(Item.id.desc()).all()
    dynamic_statuses = {(lb.status or "").lower() for lb in lockboxes if lb.status}
    status_choices = sorted(set(LOCKBOX_STATUS_OPTIONS).union(dynamic_statuses))
    return render_template(
        "lockboxes.html",
        lockboxes=lockboxes,
        q=q,
        status_options=status_choices,
    )

# --- Add (separate screen) ---
@inventory_bp.route("/lockboxes/new", methods=["GET", "POST"])
@login_required
def add_lockbox():
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

        item = Item(
            type="Lockbox",
            label=label,
            location=location or None,
            address=address or None,
            code_current=code or None,
            code_previous=None,
            status="available",
            last_action="created",
            last_action_at=datetime.utcnow(),
            last_action_by_id=getattr(current_user, "id", None),
        )
        db.session.add(item)
        db.session.flush()
        log_activity(
            "lockbox_created",
            user=current_user,
            target=item,
            summary=f"Created lockbox {label}",
            meta={
                "label": label,
                "location": location or None,
                "address": address or None,
                "code": code,
            },
            commit=False,
        )
        db.session.commit()
        flash("Lockbox added.", "success")
        return redirect(url_for("inventory.list_lockboxes"))

    return render_template("lockbox_add.html")

# --- Quick check out (requires entering current code) ---
@inventory_bp.route("/lockboxes/<int:item_id>/checkout", methods=["POST"])
@login_required
def checkout_lockbox(item_id):
    item = Item.query.get_or_404(item_id)
    if not _is_lockbox(item):
        flash("Not a lockbox.", "error")
        return redirect(url_for("inventory.list_lockboxes"))

    # Require code input (keeps code_current up to date)
    code = (request.form.get("code") or "").strip()
    if not code:
        flash("Enter the current code to check out.", "error")
        return redirect(url_for("inventory.list_lockboxes"))

    previous_assigned = item.assigned_to

    # rotate codes
    item.code_previous = item.code_current
    item.code_current = code
    item.status = "checked_out"
    item.last_action = "checked_out"
    item.last_action_at = datetime.utcnow()
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
    return redirect(url_for("inventory.list_lockboxes"))

# --- Quick check in (requires entering current code) ---
@inventory_bp.route("/lockboxes/<int:item_id>/checkin", methods=["POST"])
@login_required
def checkin_lockbox(item_id):
    item = Item.query.get_or_404(item_id)
    if not _is_lockbox(item):
        flash("Not a lockbox.", "error")
        return redirect(url_for("inventory.list_lockboxes"))

    code = (request.form.get("code") or "").strip()
    if not code:
        flash("Enter the current code to check in.", "error")
        return redirect(url_for("inventory.list_lockboxes"))

    previous_assigned = item.assigned_to
    item.code_previous = item.code_current
    item.code_current = code
    item.status = "available"
    item.last_action = "checked_in"
    item.last_action_at = datetime.utcnow()
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
    return redirect(url_for("inventory.list_lockboxes"))

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
    lb = Item.query.filter_by(id=item_id, type="Lockbox").first()
    if not lb:
        flash("Lockbox not found.", "error")
        return redirect(url_for("inventory.list_lockboxes"))

    assignee = request.form.get("assignee")
    if assignee is None:
        flash("Please provide an assignee.", "error")
        return redirect(url_for("inventory.list_lockboxes"))

    assignee_clean = assignee.strip()
    if not assignee_clean:
        flash("Please provide an assignee.", "error")
        return redirect(url_for("inventory.list_lockboxes"))

    previous_assignee = lb.assigned_to
    lb.assigned_to = assignee_clean
    lb.status = "assigned"
    lb.last_action = "assigned"
    lb.last_action_at = datetime.utcnow()
    lb.last_action_by_id = getattr(current_user, "id", None)
    log_activity(
        "lockbox_assigned",
        user=current_user,
        target=lb,
        summary=f"Assigned lockbox {lb.label} to {assignee_clean}",
        meta={
            "previous_assignee": previous_assignee,
            "assigned_to": assignee_clean,
        },
        commit=False,
    )
    db.session.commit()
    flash(f"Lockbox {lb.label} assigned to {assignee_clean}.", "success")
    return redirect(url_for("inventory.list_lockboxes"))

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
