from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import or_

from utilities.tenant_helpers import tenant_query, tenant_add, tenant_commit, tenant_rollback, get_tenant_session
from middleware.tenant_middleware import tenant_required
from utilities.database import db, SmartLock, Property, PropertyUnit, log_activity

smartlocks_bp = Blueprint(
    "smartlocks",
    __name__,
    template_folder="../templates",
    static_folder="../static"
)


def _get_smartlock_or_404(lock_id: int) -> SmartLock:
    smart_lock = get_tenant_session().get(SmartLock, lock_id)
    if smart_lock is None:
        abort(404)
    return smart_lock


@smartlocks_bp.route("/", methods=["GET"])
@login_required
@tenant_required
def list_smartlocks():
    q = (request.args.get("q") or "").strip()
    query = tenant_query(SmartLock)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                SmartLock.label.ilike(like),
                SmartLock.code.ilike(like),
                SmartLock.provider.ilike(like),
            )
        )
    locks = query.order_by(SmartLock.label.asc()).all()
    return render_template("smartlocks.html", smartlocks=locks, q=q)


@smartlocks_bp.route("/new", methods=["GET", "POST"])
@login_required
@tenant_required
def create_smartlock():
    properties = tenant_query(Property).order_by(Property.name.asc()).all()
    property_units = tenant_query(PropertyUnit).order_by(PropertyUnit.label.asc()).all()

    if request.method == "POST":
        label = (request.form.get("label") or "").strip()
        code = (request.form.get("code") or "").strip()
        provider = (request.form.get("provider") or "").strip() or None
        backup_code = (request.form.get("backup_code") or "").strip() or None
        instructions = (request.form.get("instructions") or "").strip() or None
        notes = (request.form.get("notes") or "").strip() or None
        property_id_str = (request.form.get("property_id") or "").strip()
        unit_id_str = (request.form.get("property_unit_id") or "").strip()

        errors: list[str] = []
        if not label:
            errors.append("Label is required.")
        if not code:
            errors.append("Code is required.")

        property_ref = None
        if property_id_str:
            try:
                property_ref = get_tenant_session().get(Property, int(property_id_str))
            except ValueError:
                property_ref = None
            if property_ref is None:
                errors.append("Selected property could not be found.")

        unit_ref = None
        if unit_id_str:
            try:
                unit_ref = get_tenant_session().get(PropertyUnit, int(unit_id_str))
            except ValueError:
                unit_ref = None
            if unit_ref is None:
                errors.append("Selected unit could not be found.")

        if errors:
            for message in errors:
                flash(message, "error")
            return redirect(url_for("smartlocks.create_smartlock"))

        smart_lock = SmartLock(
            label=label,
            code=code,
            provider=provider,
            backup_code=backup_code,
            instructions=instructions,
            notes=notes,
            property=property_ref,
            property_unit=unit_ref,
        )
        tenant_add(smart_lock)
        tenant_commit()
        flash("Smart lock saved.", "success")
        return redirect(url_for("smartlocks.smartlock_detail", lock_id=smart_lock.id))

    return render_template(
        "smartlock_form.html",
        smartlock=None,
        properties=properties,
        property_units=property_units,
        form_action=url_for("smartlocks.create_smartlock"),
        page_title="Add Smart Lock",
        submit_label="Save Smart Lock",
    )


@smartlocks_bp.route("/<int:lock_id>", methods=["GET"])
@login_required
@tenant_required
def smartlock_detail(lock_id: int):
    smart_lock = _get_smartlock_or_404(lock_id)
    return render_template("smartlock_detail.html", smartlock=smart_lock)

