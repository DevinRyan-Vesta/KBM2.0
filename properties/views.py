from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
    jsonify,
)
from flask_login import login_required, current_user
from sqlalchemy import or_, func

from utilities.tenant_helpers import tenant_query, tenant_add, tenant_commit, tenant_flush, tenant_rollback, get_tenant_session
from middleware.tenant_middleware import tenant_required
from utilities.database import db, Property, PropertyUnit, log_activity, Item, SmartLock

PROPERTY_TYPES = ["single_family", "multi_family", "commercial", "mixed"]

properties_bp = Blueprint(
    "properties",
    __name__,
    template_folder="../templates",
    static_folder="../static"
)


def _get_property_or_404(property_id: int) -> Property:
    property_obj = get_tenant_session().get(Property, property_id)
    if property_obj is None:
        abort(404)
    return property_obj


def _normalise_type(value: str) -> str:
    return value.lower().replace(" ", "_")


@properties_bp.route("/", methods=["GET"])
@login_required
@tenant_required
def list_properties():
    q = (request.args.get("q") or "").strip()
    query = tenant_query(Property)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Property.name.ilike(like),
                Property.address_line1.ilike(like),
                Property.city.ilike(like),
                Property.state.ilike(like),
            )
        )
    properties = query.order_by(Property.name.asc()).all()

    property_summaries = []
    for prop in properties:
        items = prop.items
        keys = [item for item in items if (item.type or "").lower() == "key"]
        lockboxes = [item for item in items if (item.type or "").lower() == "lockbox"]
        signs = [item for item in items if (item.type or "").lower() == "sign"]
        property_summaries.append(
            {
                "property": prop,
                "item_count": len(items),
                "key_count": len(keys),
                "lockbox_count": len(lockboxes),
                "sign_count": len(signs),
            }
        )

    return render_template(
        "properties.html",
        properties=property_summaries,
        q=q,
        property_types=PROPERTY_TYPES,
    )


@properties_bp.route("/new", methods=["GET", "POST"])
@login_required
@tenant_required
def create_property():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        property_type = _normalise_type(request.form.get("type") or "")
        address_line1 = (request.form.get("address_line1") or "").strip()
        address_line2 = (request.form.get("address_line2") or "").strip() or None
        city = (request.form.get("city") or "").strip() or None
        state = (request.form.get("state") or "").strip() or None
        postal_code = (request.form.get("postal_code") or "").strip() or None
        country = (request.form.get("country") or "USA").strip() or "USA"
        notes = (request.form.get("notes") or "").strip() or None

        errors: list[str] = []
        if not name:
            errors.append("Name is required.")
        if property_type not in PROPERTY_TYPES:
            errors.append("Select a valid property type.")
        if not address_line1:
            errors.append("Address line 1 is required.")

        if errors:
            for message in errors:
                flash(message, "error")
            return redirect(url_for("properties.create_property"))

        property_obj = Property(
            name=name,
            type=property_type,
            address_line1=address_line1,
            address_line2=address_line2,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country or "USA",
            notes=notes,
        )
        tenant_add(property_obj)
        tenant_flush()
        log_activity(
            "property_created",
            user=current_user,
            target=property_obj,
            summary=f"Created property {name}",
            meta={
                "name": name,
                "type": property_type,
                "address": address_line1,
                "city": city,
                "state": state,
            },
        )
        tenant_commit()
        flash("Property created.", "success")
        return redirect(url_for("properties.property_detail", property_id=property_obj.id))

    return render_template(
        "property_form.html",
        property=None,
        property_types=PROPERTY_TYPES,
        form_action=url_for("properties.create_property"),
        page_title="Add Property",
        submit_label="Save Property",
    )


@properties_bp.route("/<int:property_id>", methods=["GET"])
@login_required
@tenant_required
def property_detail(property_id: int):
    property_obj = _get_property_or_404(property_id)
    items = (
        tenant_query(Item)
        .filter(Item.property_id == property_obj.id)
        .order_by(Item.type.asc(), Item.label.asc())
        .all()
    )

    item_totals = {
        "total": len(items),
        "keys": sum(1 for item in items if (item.type or "").lower() == "key"),
        "lockboxes": sum(1 for item in items if (item.type or "").lower() == "lockbox"),
        "signs": sum(1 for item in items if (item.type or "").lower() == "sign"),
    }

    units = (
        tenant_query(PropertyUnit)
        .filter(PropertyUnit.property_id == property_obj.id)
        .order_by(PropertyUnit.label.asc())
        .all()
    )

    smart_locks = (
        tenant_query(SmartLock)
        .filter(SmartLock.property_id == property_obj.id)
        .order_by(SmartLock.label.asc())
        .all()
    )

    return render_template(
        "property_detail.html",
        property=property_obj,
        items=items,
        item_totals=item_totals,
        units=units,
        smart_locks=smart_locks,
        property_types=PROPERTY_TYPES,
    )


@properties_bp.route("/<int:property_id>/edit", methods=["GET", "POST"])
@login_required
@tenant_required
def edit_property(property_id: int):
    property_obj = _get_property_or_404(property_id)

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        property_type = _normalise_type(request.form.get("type") or "")
        address_line1 = (request.form.get("address_line1") or "").strip()
        property_obj.address_line2 = (request.form.get("address_line2") or "").strip() or None
        property_obj.city = (request.form.get("city") or "").strip() or None
        property_obj.state = (request.form.get("state") or "").strip() or None
        property_obj.postal_code = (request.form.get("postal_code") or "").strip() or None
        property_obj.country = (request.form.get("country") or "USA").strip() or "USA"
        property_obj.notes = (request.form.get("notes") or "").strip() or None

        errors: list[str] = []
        if not name:
            errors.append("Name is required.")
        if property_type not in PROPERTY_TYPES:
            errors.append("Select a valid property type.")
        if not address_line1:
            errors.append("Address line 1 is required.")

        if errors:
            for message in errors:
                flash(message, "error")
            return redirect(url_for("properties.edit_property", property_id=property_obj.id))

        property_obj.name = name
        property_obj.type = property_type
        property_obj.address_line1 = address_line1

        tenant_commit()
        flash("Property updated.", "success")
        return redirect(url_for("properties.property_detail", property_id=property_obj.id))

    return render_template(
        "property_form.html",
        property=property_obj,
        property_types=PROPERTY_TYPES,
        form_action=url_for("properties.edit_property", property_id=property_obj.id),
        page_title="Edit Property",
        submit_label="Save Changes",
    )


@properties_bp.route("/<int:property_id>/units", methods=["GET"])
@login_required
@tenant_required
def get_units(property_id: int):
    """API endpoint to get units for a property (for AJAX calls)."""
    property_obj = _get_property_or_404(property_id)
    units = tenant_query(PropertyUnit).filter_by(property_id=property_id).order_by(PropertyUnit.label).all()
    return jsonify({
        "units": [{"id": u.id, "label": u.label} for u in units]
    })


@properties_bp.route("/<int:property_id>/units", methods=["POST"])
@login_required
@tenant_required
def create_unit(property_id: int):
    property_obj = _get_property_or_404(property_id)
    label = (request.form.get("label") or "").strip()
    floor = (request.form.get("floor") or "").strip() or None
    bedrooms = request.form.get("bedrooms") or None
    bathrooms = request.form.get("bathrooms") or None
    square_feet = request.form.get("square_feet") or None
    notes = (request.form.get("notes") or "").strip() or None

    if not label:
        flash("Unit label is required.", "error")
        return redirect(url_for("properties.property_detail", property_id=property_obj.id))

    try:
        bedrooms_val = int(bedrooms) if bedrooms else None
    except ValueError:
        bedrooms_val = None
    try:
        bathrooms_val = float(bathrooms) if bathrooms else None
    except ValueError:
        bathrooms_val = None
    try:
        square_feet_val = int(square_feet) if square_feet else None
    except ValueError:
        square_feet_val = None

    unit = PropertyUnit(
        property=property_obj,
        label=label,
        floor=floor,
        bedrooms=bedrooms_val,
        bathrooms=bathrooms_val,
        square_feet=square_feet_val,
        notes=notes,
    )
    tenant_add(unit)
    tenant_commit()
    flash("Unit added.", "success")
    return redirect(url_for("properties.property_detail", property_id=property_obj.id))


@properties_bp.route("/<int:property_id>/units/<int:unit_id>", methods=["GET"])
@login_required
@tenant_required
def unit_detail(property_id: int, unit_id: int):
    """View and manage a specific property unit."""
    property_obj = _get_property_or_404(property_id)
    unit = get_tenant_session().get(PropertyUnit, unit_id)

    if unit is None or unit.property_id != property_id:
        flash("Unit not found.", "error")
        return redirect(url_for("properties.property_detail", property_id=property_id))

    # Get all keys associated with this unit
    keys = tenant_query(Item).filter_by(
        type="Key",
        property_unit_id=unit_id
    ).all()

    return render_template(
        "unit_detail.html",
        property=property_obj,
        unit=unit,
        keys=keys
    )


@properties_bp.route("/<int:property_id>/units/<int:unit_id>/edit", methods=["POST"])
@login_required
@tenant_required
def edit_unit(property_id: int, unit_id: int):
    """Edit a property unit."""
    property_obj = _get_property_or_404(property_id)
    unit = get_tenant_session().get(PropertyUnit, unit_id)

    if unit is None or unit.property_id != property_id:
        flash("Unit not found.", "error")
        return redirect(url_for("properties.property_detail", property_id=property_id))

    label = (request.form.get("label") or "").strip()
    if not label:
        flash("Unit label is required.", "error")
        return redirect(url_for("properties.unit_detail", property_id=property_id, unit_id=unit_id))

    floor = (request.form.get("floor") or "").strip() or None
    bedrooms = request.form.get("bedrooms") or None
    bathrooms = request.form.get("bathrooms") or None
    square_feet = request.form.get("square_feet") or None
    notes = (request.form.get("notes") or "").strip() or None

    try:
        bedrooms_val = int(bedrooms) if bedrooms else None
    except ValueError:
        bedrooms_val = None
    try:
        bathrooms_val = float(bathrooms) if bathrooms else None
    except ValueError:
        bathrooms_val = None
    try:
        square_feet_val = int(square_feet) if square_feet else None
    except ValueError:
        square_feet_val = None

    unit.label = label
    unit.floor = floor
    unit.bedrooms = bedrooms_val
    unit.bathrooms = bathrooms_val
    unit.square_feet = square_feet_val
    unit.notes = notes

    tenant_commit()
    flash("Unit updated successfully.", "success")
    return redirect(url_for("properties.unit_detail", property_id=property_id, unit_id=unit_id))


@properties_bp.route("/<int:property_id>/units/<int:unit_id>/delete", methods=["POST"])
@login_required
@tenant_required
def delete_unit(property_id: int, unit_id: int):
    """Delete a property unit."""
    from flask_login import current_user

    # Check if user is admin
    if not hasattr(current_user, 'role') or current_user.role != 'admin':
        flash("You must be an admin to delete units.", "error")
        return redirect(url_for("properties.property_detail", property_id=property_id))

    property_obj = _get_property_or_404(property_id)
    unit = get_tenant_session().get(PropertyUnit, unit_id)

    if unit is None or unit.property_id != property_id:
        flash("Unit not found.", "error")
        return redirect(url_for("properties.property_detail", property_id=property_id))

    # Check if any keys are associated with this unit
    keys_count = tenant_query(Item).filter_by(
        type="Key",
        property_unit_id=unit_id
    ).count()

    if keys_count > 0:
        flash(f"Cannot delete unit: {keys_count} key(s) are associated with it. Please reassign or delete the keys first.", "error")
        return redirect(url_for("properties.unit_detail", property_id=property_id, unit_id=unit_id))

    unit_label = unit.label
    get_tenant_session().delete(unit)
    tenant_commit()

    flash(f"Unit '{unit_label}' deleted successfully.", "success")
    return redirect(url_for("properties.property_detail", property_id=property_id))


@properties_bp.route("/api/search", methods=["GET"])
@login_required
@tenant_required
def search_properties():
    q = (request.args.get("q") or "").strip()
    query = tenant_query(Property)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Property.name.ilike(like),
                Property.address_line1.ilike(like),
                Property.city.ilike(like),
            )
        )
    results = query.order_by(Property.name.asc()).limit(20).all()
    payload = [
        {
            "id": prop.id,
            "name": prop.name,
            "address": ", ".join(filter(None, [prop.address_line1, prop.city, prop.state])),
            "type": prop.type,
        }
        for prop in results
    ]
    return jsonify(payload)

