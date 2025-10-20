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
from flask_login import login_required
from sqlalchemy import or_, func

from utilities.database import db, Property, PropertyUnit, Item, SmartLock

PROPERTY_TYPES = ["single_family", "multi_family", "commercial", "mixed"]

properties_bp = Blueprint(
    "properties",
    __name__,
    template_folder="../templates",
    static_folder="../static"
)


def _get_property_or_404(property_id: int) -> Property:
    property_obj = db.session.get(Property, property_id)
    if property_obj is None:
        abort(404)
    return property_obj


def _normalise_type(value: str) -> str:
    return value.lower().replace(" ", "_")


@properties_bp.route("/", methods=["GET"])
@login_required
def list_properties():
    q = (request.args.get("q") or "").strip()
    query = Property.query
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
        db.session.add(property_obj)
        db.session.commit()
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
def property_detail(property_id: int):
    property_obj = _get_property_or_404(property_id)
    items = (
        Item.query
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
        PropertyUnit.query
        .filter(PropertyUnit.property_id == property_obj.id)
        .order_by(PropertyUnit.label.asc())
        .all()
    )

    smart_locks = (
        SmartLock.query
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

        db.session.commit()
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


@properties_bp.route("/<int:property_id>/units", methods=["POST"])
@login_required
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
    db.session.add(unit)
    db.session.commit()
    flash("Unit added.", "success")
    return redirect(url_for("properties.property_detail", property_id=property_obj.id))


@properties_bp.route("/api/search", methods=["GET"])
@login_required
def search_properties():
    q = (request.args.get("q") or "").strip()
    query = Property.query
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

