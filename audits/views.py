# audits/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_login import login_required, current_user
from utilities.tenant_helpers import tenant_required, tenant_query, tenant_add, tenant_commit, tenant_rollback
from utilities.database import Audit, AuditItem, Item, db, utc_now, log_activity
from datetime import datetime
import csv
from io import StringIO

audits_bp = Blueprint("audits", __name__, url_prefix="/audits")


def _require_admin():
    """Helper to check if current user is admin"""
    role = (getattr(current_user, "role", "") or "").lower()
    if role not in ("admin", "owner"):
        from flask import abort
        abort(403)


@audits_bp.route("/", methods=["GET"])
@login_required
@tenant_required
def list_audits():
    """List all audits"""
    audits = (
        tenant_query(Audit)
        .order_by(Audit.created_at.desc())
        .all()
    )
    return render_template("audits/list.html", audits=audits)


@audits_bp.route("/create", methods=["POST"])
@login_required
@tenant_required
def create_audit():
    """Create a new audit with all current keys"""
    _require_admin()

    # Get all keys from inventory
    keys = tenant_query(Item).filter_by(type="Key").order_by(Item.key_hook_number, Item.label).all()

    if not keys:
        flash("No keys found in inventory to audit.", "error")
        return redirect(url_for("audits.list_audits"))

    # Create audit
    audit = Audit(
        audit_date=utc_now(),
        created_by_user_id=current_user.id,
        status="pending",
    )
    tenant_add(audit)
    tenant_commit()  # Commit to get audit ID

    # Create audit items for each key
    for key in keys:
        audit_item = AuditItem(
            audit_id=audit.id,
            item_id=key.id,
            expected_location=key.key_hook_number or "",
            expected_quantity=key.total_copies or 0,
        )
        tenant_add(audit_item)

    tenant_commit()

    log_activity(
        "audit_created",
        user=current_user,
        target_type="Audit",
        target_id=audit.id,
        summary=f"Created audit with {len(keys)} keys",
        commit=True,
    )

    flash(f"Audit created with {len(keys)} keys.", "success")
    return redirect(url_for("audits.view_audit", audit_id=audit.id))


@audits_bp.route("/<int:audit_id>", methods=["GET"])
@login_required
@tenant_required
def view_audit(audit_id: int):
    """View audit details"""
    audit = tenant_query(Audit).filter_by(id=audit_id).first()
    if not audit:
        flash("Audit not found.", "error")
        return redirect(url_for("audits.list_audits"))

    # Get audit items with their associated items
    audit_items = (
        tenant_query(AuditItem)
        .filter_by(audit_id=audit_id)
        .join(Item, AuditItem.item_id == Item.id)
        .order_by(Item.key_hook_number, Item.label)
        .all()
    )

    # Calculate statistics
    total_items = len(audit_items)
    audited_items = sum(1 for ai in audit_items if ai.audited_at)
    discrepancies = sum(1 for ai in audit_items if ai.discrepancy_type and ai.discrepancy_type != "none")

    return render_template(
        "audits/view.html",
        audit=audit,
        audit_items=audit_items,
        total_items=total_items,
        audited_items=audited_items,
        discrepancies=discrepancies,
    )


@audits_bp.route("/<int:audit_id>/print", methods=["GET"])
@login_required
@tenant_required
def print_audit(audit_id: int):
    """Print-friendly audit sheet"""
    audit = tenant_query(Audit).filter_by(id=audit_id).first()
    if not audit:
        flash("Audit not found.", "error")
        return redirect(url_for("audits.list_audits"))

    # Get audit items with their associated items
    audit_items = (
        tenant_query(AuditItem)
        .filter_by(audit_id=audit_id)
        .join(Item, AuditItem.item_id == Item.id)
        .order_by(Item.key_hook_number, Item.label)
        .all()
    )

    return render_template(
        "audits/print.html",
        audit=audit,
        audit_items=audit_items,
    )


@audits_bp.route("/<int:audit_id>/input", methods=["GET", "POST"])
@login_required
@tenant_required
def input_results(audit_id: int):
    """Input audit results"""
    _require_admin()

    audit = tenant_query(Audit).filter_by(id=audit_id).first()
    if not audit:
        flash("Audit not found.", "error")
        return redirect(url_for("audits.list_audits"))

    if request.method == "GET":
        # Get audit items
        audit_items = (
            tenant_query(AuditItem)
            .filter_by(audit_id=audit_id)
            .join(Item, AuditItem.item_id == Item.id)
            .order_by(Item.key_hook_number, Item.label)
            .all()
        )
        return render_template("audits/input.html", audit=audit, audit_items=audit_items)

    # POST - save results
    try:
        audit.status = "in_progress"

        # Process each audit item
        for key, value in request.form.items():
            if key.startswith("actual_location_"):
                item_id = int(key.replace("actual_location_", ""))
                audit_item = tenant_query(AuditItem).filter_by(audit_id=audit_id, id=item_id).first()

                if audit_item:
                    actual_location = value.strip()
                    actual_quantity_str = request.form.get(f"actual_quantity_{item_id}", "").strip()

                    # Parse quantity
                    try:
                        actual_quantity = int(actual_quantity_str) if actual_quantity_str else None
                    except ValueError:
                        actual_quantity = None

                    audit_item.actual_location = actual_location if actual_location else None
                    audit_item.actual_quantity = actual_quantity
                    audit_item.audited_at = utc_now()

                    # Detect discrepancies
                    discrepancy_type = "none"
                    if actual_location is None and actual_quantity is None:
                        discrepancy_type = "missing"
                    elif actual_location and audit_item.expected_location and actual_location != audit_item.expected_location:
                        discrepancy_type = "wrong_location"
                    elif actual_quantity is not None and audit_item.expected_quantity != actual_quantity:
                        discrepancy_type = "quantity_mismatch"

                    audit_item.discrepancy_type = discrepancy_type
                    audit_item.notes = request.form.get(f"notes_{item_id}", "").strip()

        tenant_commit()

        log_activity(
            "audit_updated",
            user=current_user,
            target_type="Audit",
            target_id=audit.id,
            summary=f"Updated audit results",
            commit=True,
        )

        flash("Audit results saved.", "success")
        return redirect(url_for("audits.view_audit", audit_id=audit_id))

    except Exception as e:
        tenant_rollback()
        flash(f"Error saving audit results: {str(e)}", "error")
        return redirect(url_for("audits.input_results", audit_id=audit_id))


@audits_bp.route("/<int:audit_id>/complete", methods=["POST"])
@login_required
@tenant_required
def complete_audit(audit_id: int):
    """Mark audit as completed"""
    _require_admin()

    audit = tenant_query(Audit).filter_by(id=audit_id).first()
    if not audit:
        flash("Audit not found.", "error")
        return redirect(url_for("audits.list_audits"))

    audit.status = "completed"
    audit.completed_at = utc_now()
    tenant_commit()

    log_activity(
        "audit_completed",
        user=current_user,
        target_type="Audit",
        target_id=audit.id,
        summary=f"Completed audit",
        commit=True,
    )

    flash("Audit marked as completed.", "success")
    return redirect(url_for("audits.view_audit", audit_id=audit_id))


@audits_bp.route("/<int:audit_id>/apply", methods=["POST"])
@login_required
@tenant_required
def apply_audit(audit_id: int):
    """Apply audit results to inventory"""
    _require_admin()

    audit = tenant_query(Audit).filter_by(id=audit_id).first()
    if not audit:
        flash("Audit not found.", "error")
        return redirect(url_for("audits.list_audits"))

    # Get all audit items with discrepancies
    audit_items = (
        tenant_query(AuditItem)
        .filter_by(audit_id=audit_id)
        .filter(AuditItem.discrepancy_type.isnot(None))
        .filter(AuditItem.discrepancy_type != "none")
        .all()
    )

    if not audit_items:
        flash("No discrepancies to apply.", "info")
        return redirect(url_for("audits.view_audit", audit_id=audit_id))

    updated_count = 0
    for audit_item in audit_items:
        item = tenant_query(Item).filter_by(id=audit_item.item_id).first()
        if item:
            # Update location if wrong
            if audit_item.discrepancy_type == "wrong_location" and audit_item.actual_location:
                item.key_hook_number = audit_item.actual_location
                updated_count += 1

            # Update quantity if mismatch
            if audit_item.discrepancy_type == "quantity_mismatch" and audit_item.actual_quantity is not None:
                item.total_copies = audit_item.actual_quantity
                updated_count += 1

            # Log activity
            log_activity(
                "item_updated_from_audit",
                user=current_user,
                target_type="Item",
                target_id=item.id,
                summary=f"Updated {item.label} from audit",
                meta={
                    "audit_id": audit_id,
                    "discrepancy_type": audit_item.discrepancy_type,
                },
                commit=False,
            )

    tenant_commit()

    flash(f"Applied audit results. Updated {updated_count} items.", "success")
    return redirect(url_for("audits.view_audit", audit_id=audit_id))


@audits_bp.route("/low-copy-report", methods=["GET"])
@login_required
@tenant_required
def low_copy_report():
    """Show keys with less than 6 total copies"""
    threshold = request.args.get("threshold", 6, type=int)

    keys = (
        tenant_query(Item)
        .filter(Item.type == "Key")
        .filter(Item.total_copies < threshold)
        .order_by(Item.total_copies, Item.label)
        .all()
    )

    return render_template("audits/low_copy_report.html", keys=keys, threshold=threshold)


@audits_bp.route("/low-copy-report/export", methods=["GET"])
@login_required
@tenant_required
def export_low_copy_report():
    """Export low copy report as CSV"""
    threshold = request.args.get("threshold", 6, type=int)

    keys = (
        tenant_query(Item)
        .filter(Item.type == "Key")
        .filter(Item.total_copies < threshold)
        .order_by(Item.total_copies, Item.label)
        .all()
    )

    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Key Label', 'Custom ID', 'Key Hook #', 'Total Copies', 'Keycode', 'Location', 'Property'])

    for key in keys:
        property_name = key.property.name if key.property else ''
        writer.writerow([
            key.label,
            key.custom_id or '',
            key.key_hook_number or '',
            key.total_copies or 0,
            key.keycode or '',
            key.location or '',
            property_name,
        ])

    # Create response
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=low_copy_keys_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

    return response


@audits_bp.route("/reorganize", methods=["GET", "POST"])
@login_required
@tenant_required
def reorganize_keys():
    """Help reorganize keybox and assign new keyhook positions"""
    _require_admin()

    if request.method == "GET":
        # Get all keys grouped by property
        keys = (
            tenant_query(Item)
            .filter_by(type="Key")
            .order_by(Item.property_id, Item.label)
            .all()
        )

        # Group keys by property
        from collections import defaultdict
        keys_by_property = defaultdict(list)
        for key in keys:
            property_name = key.property.name if key.property else "(No Property)"
            keys_by_property[property_name].append(key)

        # Sort properties
        sorted_properties = sorted(keys_by_property.items())

        return render_template("audits/reorganize.html", keys_by_property=sorted_properties)

    # POST - apply reorganization
    try:
        # Get reorganization data from form
        for key, value in request.form.items():
            if key.startswith("keyhook_"):
                item_id = int(key.replace("keyhook_", ""))
                new_keyhook = value.strip()

                item = tenant_query(Item).filter_by(id=item_id, type="Key").first()
                if item and new_keyhook:
                    old_keyhook = item.key_hook_number
                    item.key_hook_number = new_keyhook

                    log_activity(
                        "key_reorganized",
                        user=current_user,
                        target_type="Item",
                        target_id=item.id,
                        summary=f"Moved {item.label} from hook {old_keyhook} to {new_keyhook}",
                        commit=False,
                    )

        tenant_commit()
        flash("Key reorganization applied successfully.", "success")
        return redirect(url_for("inventory.list_keys"))

    except Exception as e:
        tenant_rollback()
        flash(f"Error applying reorganization: {str(e)}", "error")
        return redirect(url_for("audits.reorganize_keys"))
