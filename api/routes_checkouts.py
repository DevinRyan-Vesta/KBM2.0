"""Checkout / assignment history (read-only — mutations happen via item actions)."""

from flask import jsonify, request

from api import api_bp
from api.helpers import api_tenant_required, error, paginate
from utilities.database import ItemCheckout, utc_now
from utilities.tenant_helpers import get_tenant_session, tenant_query


def _serialize(checkout: ItemCheckout) -> dict:
    payload = checkout.to_dict()
    if checkout.item:
        payload["item"] = {
            "id": checkout.item.id,
            "custom_id": checkout.item.custom_id,
            "type": checkout.item.type,
            "label": checkout.item.label,
        }
    payload["contact_id"] = checkout.contact_id
    return payload


@api_bp.get("/checkouts")
@api_tenant_required
def list_checkouts():
    query = tenant_query(ItemCheckout)

    active = request.args.get("active")
    if active is not None:
        query = query.filter(ItemCheckout.is_active.is_(active.lower() in ("true", "1", "yes")))

    item_id = request.args.get("item_id", type=int)
    if item_id:
        query = query.filter(ItemCheckout.item_id == item_id)

    contact_id = request.args.get("contact_id", type=int)
    if contact_id:
        query = query.filter(ItemCheckout.contact_id == contact_id)

    person = request.args.get("person")
    if person:
        query = query.filter(ItemCheckout.checked_out_to.ilike(f"%{person}%"))

    if request.args.get("overdue", "").lower() in ("true", "1", "yes"):
        query = query.filter(
            ItemCheckout.is_active.is_(True),
            ItemCheckout.expected_return_date.isnot(None),
            ItemCheckout.expected_return_date < utc_now(),
        )

    query = query.order_by(ItemCheckout.checked_out_at.desc())

    page_rows, meta = paginate(query)
    return jsonify({
        "checkouts": [_serialize(c) for c in page_rows],
        "pagination": meta,
    })


@api_bp.get("/checkouts/<int:checkout_id>")
@api_tenant_required
def get_checkout(checkout_id: int):
    checkout = get_tenant_session().get(ItemCheckout, checkout_id)
    if checkout is None:
        raise error(404, "not_found", f"Checkout {checkout_id} not found.")
    return jsonify(_serialize(checkout))
