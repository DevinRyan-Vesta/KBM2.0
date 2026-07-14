"""Smart locks CRUD (image uploads stay web-only)."""

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
from utilities.database import db, Property, PropertyUnit, SmartLock, log_activity
from utilities.tenant_helpers import get_tenant_session, tenant_add, tenant_commit, tenant_query

LOCK_STR_FIELDS = ("label", "provider", "code", "backup_code", "instructions", "notes",
                   "model_number", "serial_number", "pairing_code", "qr_code_data")


def _get_lock_or_404(lock_id: int) -> SmartLock:
    lock = get_tenant_session().get(SmartLock, lock_id)
    if lock is None:
        raise error(404, "not_found", f"Smart lock {lock_id} not found.")
    return lock


def _apply_fields(lock: SmartLock, body: dict):
    for field in LOCK_STR_FIELDS:
        if field in body:
            max_len = None if field in ("instructions", "notes", "qr_code_data") else 255
            setattr(lock, field, clean_str(body.get(field), field, max_len))

    if "property_id" in body:
        pid = clean_int(body.get("property_id"), "property_id")
        if pid is not None and get_tenant_session().get(Property, pid) is None:
            raise error(400, "invalid_field", f"Property {pid} not found.")
        lock.property_id = pid
    if "property_unit_id" in body:
        uid = clean_int(body.get("property_unit_id"), "property_unit_id")
        if uid is not None:
            unit = get_tenant_session().get(PropertyUnit, uid)
            if unit is None:
                raise error(400, "invalid_field", f"Property unit {uid} not found.")
            if lock.property_id and unit.property_id != lock.property_id:
                raise error(400, "invalid_field", "Selected unit does not belong to the chosen property.")
        lock.property_unit_id = uid

    if not lock.label:
        raise error(400, "invalid_field", "'label' is required.")
    if not lock.code:
        raise error(400, "invalid_field", "'code' is required.")


@api_bp.get("/smart-locks")
@api_tenant_required
def list_smart_locks():
    query = tenant_query(SmartLock)

    property_id = request.args.get("property_id", type=int)
    if property_id:
        query = query.filter(SmartLock.property_id == property_id)

    q = request.args.get("q")
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(
            SmartLock.label.ilike(like),
            SmartLock.provider.ilike(like),
            SmartLock.model_number.ilike(like),
        ))

    query = query.order_by(SmartLock.label.asc())
    rows, meta = paginate(query)
    return list_response("smart_locks", rows, meta)


@api_bp.post("/smart-locks")
@api_tenant_required
def create_smart_lock():
    body = get_json_body()
    lock = SmartLock()
    _apply_fields(lock, body)
    tenant_add(lock)
    log_activity("smart_lock_added", user=g.api_user, target=lock,
                 summary=f"Added smart lock {lock.label} via API", commit=False)
    tenant_commit()
    return jsonify(lock.to_dict()), 201


@api_bp.get("/smart-locks/<int:lock_id>")
@api_tenant_required
def get_smart_lock(lock_id: int):
    lock = _get_lock_or_404(lock_id)
    payload = lock.to_dict()
    payload["images"] = [img.to_dict() for img in lock.images]
    return jsonify(payload)


@api_bp.patch("/smart-locks/<int:lock_id>")
@api_tenant_required
def update_smart_lock(lock_id: int):
    lock = _get_lock_or_404(lock_id)
    body = get_json_body()
    _apply_fields(lock, body)
    log_activity("smart_lock_updated", user=g.api_user, target=lock,
                 summary=f"Updated smart lock {lock.label} via API",
                 meta={"fields": sorted(set(body.keys()))}, commit=False)
    tenant_commit()
    return jsonify(lock.to_dict())


@api_bp.delete("/smart-locks/<int:lock_id>")
@api_tenant_required
def delete_smart_lock(lock_id: int):
    require_admin()
    lock = _get_lock_or_404(lock_id)
    label, lid = lock.label, lock.id
    get_tenant_session().delete(lock)
    log_activity("smart_lock_deleted", user=g.api_user, target_type="SmartLock", target_id=lid,
                 summary=f"Deleted smart lock {label} via API", commit=False)
    tenant_commit()
    return jsonify({"deleted": True, "id": lid})
