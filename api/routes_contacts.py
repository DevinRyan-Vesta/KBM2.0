"""Contacts CRUD."""

from flask import g, jsonify, request

from api import api_bp
from api.helpers import (
    api_tenant_required,
    clean_str,
    error,
    get_json_body,
    list_response,
    paginate,
    require_admin,
)
from utilities.database import db, Contact, ItemCheckout, log_activity
from utilities.tenant_helpers import get_tenant_session, tenant_add, tenant_commit, tenant_query

CONTACT_STR_FIELDS = ("contact_type", "name", "company", "email", "phone", "notes")


def _get_contact_or_404(contact_id: int) -> Contact:
    contact = get_tenant_session().get(Contact, contact_id)
    if contact is None:
        raise error(404, "not_found", f"Contact {contact_id} not found.")
    return contact


def _apply_fields(contact: Contact, body: dict):
    for field in CONTACT_STR_FIELDS:
        if field in body:
            setattr(contact, field, clean_str(body.get(field), field, 255))
    if not contact.name:
        raise error(400, "invalid_field", "'name' is required.")
    if not contact.contact_type:
        contact.contact_type = "other"


@api_bp.get("/contacts")
@api_tenant_required
def list_contacts():
    query = tenant_query(Contact)

    contact_type = request.args.get("type")
    if contact_type:
        query = query.filter(Contact.contact_type == contact_type)

    q = request.args.get("q")
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(
            Contact.name.ilike(like),
            Contact.company.ilike(like),
            Contact.email.ilike(like),
            Contact.phone.ilike(like),
        ))

    query = query.order_by(Contact.name.asc())
    rows, meta = paginate(query)
    return list_response("contacts", rows, meta)


@api_bp.post("/contacts")
@api_tenant_required
def create_contact():
    body = get_json_body()
    contact = Contact()
    _apply_fields(contact, body)
    tenant_add(contact)
    log_activity("contact_added", user=g.api_user, target=contact,
                 summary=f"Added contact {contact.name} via API", commit=False)
    tenant_commit()
    return jsonify(contact.to_dict()), 201


@api_bp.get("/contacts/<int:contact_id>")
@api_tenant_required
def get_contact(contact_id: int):
    contact = _get_contact_or_404(contact_id)
    payload = contact.to_dict()
    payload["active_checkouts"] = [
        c.to_dict() for c in tenant_query(ItemCheckout)
        .filter_by(contact_id=contact.id, is_active=True)
        .order_by(ItemCheckout.checked_out_at.desc())
        .all()
    ]
    return jsonify(payload)


@api_bp.patch("/contacts/<int:contact_id>")
@api_tenant_required
def update_contact(contact_id: int):
    contact = _get_contact_or_404(contact_id)
    body = get_json_body()
    _apply_fields(contact, body)
    log_activity("contact_updated", user=g.api_user, target=contact,
                 summary=f"Updated contact {contact.name} via API",
                 meta={"fields": sorted(set(body.keys()))}, commit=False)
    tenant_commit()
    return jsonify(contact.to_dict())


@api_bp.delete("/contacts/<int:contact_id>")
@api_tenant_required
def delete_contact(contact_id: int):
    require_admin()
    contact = _get_contact_or_404(contact_id)

    active = tenant_query(ItemCheckout).filter_by(contact_id=contact.id, is_active=True).count()
    if active:
        raise error(409, "contact_in_use",
                    f"This contact has {active} active checkout(s). Check items in first.")

    name, cid = contact.name, contact.id
    get_tenant_session().delete(contact)
    log_activity("contact_deleted", user=g.api_user, target_type="Contact", target_id=cid,
                 summary=f"Deleted contact {name} via API", commit=False)
    tenant_commit()
    return jsonify({"deleted": True, "id": cid})
