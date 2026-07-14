"""Properties and property units CRUD."""

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
    require_admin,
)
from utilities.database import db, Item, Property, PropertyUnit, SmartLock, log_activity
from utilities.tenant_helpers import get_tenant_session, tenant_add, tenant_commit, tenant_query

PROPERTY_TYPES = ("single_family", "multi_family", "condo", "apartment", "commercial", "land", "other")
PROPERTY_STR_FIELDS = ("name", "type", "address_line1", "address_line2", "city",
                       "state", "postal_code", "country", "notes")
UNIT_STR_FIELDS = ("label", "floor", "notes")


def _get_property_or_404(property_id: int) -> Property:
    prop = get_tenant_session().get(Property, property_id)
    if prop is None:
        raise error(404, "not_found", f"Property {property_id} not found.")
    return prop


def _get_unit_or_404(unit_id: int) -> PropertyUnit:
    unit = get_tenant_session().get(PropertyUnit, unit_id)
    if unit is None:
        raise error(404, "not_found", f"Property unit {unit_id} not found.")
    return unit


def _apply_property_fields(prop: Property, body: dict, *, creating: bool):
    for field in PROPERTY_STR_FIELDS:
        if field in body:
            setattr(prop, field, clean_str(body.get(field), field, 255))
    for field in ("latitude", "longitude"):
        if field in body:
            value = body.get(field)
            if value is not None and not isinstance(value, (int, float)):
                raise error(400, "invalid_field", f"'{field}' must be a number.")
            setattr(prop, field, value)

    if not prop.name:
        raise error(400, "invalid_field", "'name' is required.")
    if not prop.address_line1:
        raise error(400, "invalid_field", "'address_line1' is required.")
    if creating and not prop.type:
        prop.type = "single_family"


@api_bp.get("/properties")
@api_tenant_required
def list_properties():
    query = tenant_query(Property)
    q = request.args.get("q")
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(
            Property.name.ilike(like),
            Property.address_line1.ilike(like),
            Property.city.ilike(like),
        ))
    query = query.order_by(Property.name.asc())
    rows, meta = paginate(query)
    return list_response("properties", rows, meta)


@api_bp.post("/properties")
@api_tenant_required
def create_property():
    body = get_json_body()
    prop = Property()
    _apply_property_fields(prop, body, creating=True)
    tenant_add(prop)
    log_activity("property_added", user=g.api_user, target=prop,
                 summary=f"Added property {prop.name} via API", commit=False)
    tenant_commit()
    return jsonify(prop.to_dict()), 201


@api_bp.get("/properties/<int:property_id>")
@api_tenant_required
def get_property(property_id: int):
    prop = _get_property_or_404(property_id)
    payload = prop.to_dict()
    payload["units"] = [u.to_dict() for u in prop.units]
    payload["item_count"] = tenant_query(Item).filter_by(property_id=prop.id).count()
    payload["smart_lock_count"] = tenant_query(SmartLock).filter_by(property_id=prop.id).count()
    return jsonify(payload)


@api_bp.patch("/properties/<int:property_id>")
@api_tenant_required
def update_property(property_id: int):
    prop = _get_property_or_404(property_id)
    body = get_json_body()
    _apply_property_fields(prop, body, creating=False)
    log_activity("property_updated", user=g.api_user, target=prop,
                 summary=f"Updated property {prop.name} via API",
                 meta={"fields": sorted(set(body.keys()))}, commit=False)
    tenant_commit()
    return jsonify(prop.to_dict())


@api_bp.delete("/properties/<int:property_id>")
@api_tenant_required
def delete_property(property_id: int):
    require_admin()
    prop = _get_property_or_404(property_id)

    linked_items = tenant_query(Item).filter_by(property_id=prop.id).count()
    if linked_items:
        raise error(409, "property_in_use",
                    f"{linked_items} item(s) are linked to this property. Unlink them first.")

    name, pid = prop.name, prop.id
    get_tenant_session().delete(prop)
    log_activity("property_deleted", user=g.api_user, target_type="Property", target_id=pid,
                 summary=f"Deleted property {name} via API", commit=False)
    tenant_commit()
    return jsonify({"deleted": True, "id": pid})


# --- Units --------------------------------------------------------------------

@api_bp.get("/properties/<int:property_id>/units")
@api_tenant_required
def list_units(property_id: int):
    prop = _get_property_or_404(property_id)
    return jsonify({"units": [u.to_dict() for u in prop.units]})


@api_bp.post("/properties/<int:property_id>/units")
@api_tenant_required
def create_unit(property_id: int):
    prop = _get_property_or_404(property_id)
    body = get_json_body()

    unit = PropertyUnit(property_id=prop.id)
    _apply_unit_fields(unit, body)
    if not unit.label:
        raise error(400, "invalid_field", "'label' is required.")

    tenant_add(unit)
    log_activity("property_unit_added", user=g.api_user, target=unit,
                 summary=f"Added unit {unit.label} to property {prop.name} via API", commit=False)
    tenant_commit()
    return jsonify(unit.to_dict()), 201


@api_bp.get("/units/<int:unit_id>")
@api_tenant_required
def get_unit(unit_id: int):
    return jsonify(_get_unit_or_404(unit_id).to_dict())


@api_bp.patch("/units/<int:unit_id>")
@api_tenant_required
def update_unit(unit_id: int):
    unit = _get_unit_or_404(unit_id)
    body = get_json_body()
    _apply_unit_fields(unit, body)
    if not unit.label:
        raise error(400, "invalid_field", "'label' cannot be blank.")
    log_activity("property_unit_updated", user=g.api_user, target=unit,
                 summary=f"Updated unit {unit.label} via API", commit=False)
    tenant_commit()
    return jsonify(unit.to_dict())


@api_bp.delete("/units/<int:unit_id>")
@api_tenant_required
def delete_unit(unit_id: int):
    require_admin()
    unit = _get_unit_or_404(unit_id)

    linked_items = tenant_query(Item).filter_by(property_unit_id=unit.id).count()
    if linked_items:
        raise error(409, "unit_in_use",
                    f"{linked_items} item(s) are linked to this unit. Unlink them first.")

    label, uid = unit.label, unit.id
    get_tenant_session().delete(unit)
    log_activity("property_unit_deleted", user=g.api_user, target_type="PropertyUnit", target_id=uid,
                 summary=f"Deleted unit {label} via API", commit=False)
    tenant_commit()
    return jsonify({"deleted": True, "id": uid})


def _apply_unit_fields(unit: PropertyUnit, body: dict):
    for field in UNIT_STR_FIELDS:
        if field in body:
            setattr(unit, field, clean_str(body.get(field), field, 255))
    if "bedrooms" in body:
        unit.bedrooms = clean_int(body.get("bedrooms"), "bedrooms")
    if "square_feet" in body:
        unit.square_feet = clean_int(body.get("square_feet"), "square_feet")
    if "bathrooms" in body:
        value = body.get("bathrooms")
        if value is not None and not isinstance(value, (int, float)):
            raise error(400, "invalid_field", "'bathrooms' must be a number.")
        unit.bathrooms = value
