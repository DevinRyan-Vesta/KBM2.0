"""Audit sessions (read-only in the API — audits are conducted in the web UI)."""

from flask import jsonify, request

from api import api_bp
from api.helpers import api_tenant_required, error, list_response, paginate
from utilities.database import Audit
from utilities.tenant_helpers import get_tenant_session, tenant_query


@api_bp.get("/audits")
@api_tenant_required
def list_audits():
    query = tenant_query(Audit)

    status = request.args.get("status")
    if status:
        query = query.filter(Audit.status == status)

    query = query.order_by(Audit.created_at.desc())
    rows, meta = paginate(query)
    return list_response("audits", rows, meta)


@api_bp.get("/audits/<int:audit_id>")
@api_tenant_required
def get_audit(audit_id: int):
    audit = get_tenant_session().get(Audit, audit_id)
    if audit is None:
        raise error(404, "not_found", f"Audit {audit_id} not found.")

    payload = audit.to_dict()
    payload["items"] = [ai.to_dict() for ai in audit.items]
    payload["discrepancy_count"] = sum(
        1 for ai in audit.items
        if ai.discrepancy_type and ai.discrepancy_type != "none"
    )
    return jsonify(payload)
