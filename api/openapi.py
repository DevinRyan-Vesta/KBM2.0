"""OpenAPI 3.0 spec for the KBM API, built as plain data.

Kept deliberately compact: helper functions generate the repetitive parts
(pagination params, standard error responses, CRUD path items).
"""

from config import APP_VERSION

BEARER = [{"bearerAuth": []}]

PAGINATION_PARAMS = [
    {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
    {"name": "per_page", "in": "query", "schema": {"type": "integer", "default": 25, "maximum": 100}},
]


def _resp(description, status="200"):
    return {status: {"description": description}}


def _errors(*statuses):
    messages = {
        "400": "Validation error",
        "401": "Missing or invalid token",
        "403": "Insufficient permissions",
        "404": "Not found",
        "409": "Conflict (state prevents the operation)",
        "429": "Rate limited",
    }
    return {s: {"description": messages[s]} for s in statuses}


def _op(summary, *, tag, params=None, body=None, responses=None, security=True, description=None):
    op = {"summary": summary, "tags": [tag], "responses": responses or _resp("OK")}
    if description:
        op["description"] = description
    if params:
        op["parameters"] = params
    if body:
        op["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": body}},
        }
    if security:
        op["security"] = BEARER
    return op


def _obj(props, required=None):
    schema = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


S = {"type": "string"}
I = {"type": "integer"}
B = {"type": "boolean"}
N = {"type": "number"}
DATE = {"type": "string", "format": "date", "description": "YYYY-MM-DD or ISO-8601"}


def build_spec():
    id_param = lambda name, desc: {"name": name, "in": "path", "required": True, "schema": S if name == "item_ref" else I, "description": desc}  # noqa: E731

    item_ref = id_param("item_ref", "Numeric item id or custom id (e.g. KA042)")

    paths = {}

    # --- Meta / auth ---
    paths["/"] = {"get": _op("API index and orientation", tag="Meta", security=False)}
    paths["/me"] = {"get": _op("Identify the current token's user", tag="Meta")}
    paths["/auth/tokens"] = {
        "post": _op(
            "Create an API token (email + PIN)",
            tag="Auth", security=False,
            description="Call on your company subdomain. App admins call on the root domain. "
                        "The raw token is returned exactly once. Rate limited.",
            body=_obj({"email": S, "pin": S, "name": S, "expires_in_days": I}, ["email", "pin"]),
            responses={**_resp("Token created (includes raw token)", "201"), **_errors("400", "401", "429")},
        ),
        "get": _op("List tokens (own; admins see the whole account)", tag="Auth"),
    }
    paths["/auth/tokens/{token_id}"] = {
        "delete": _op("Revoke a token", tag="Auth",
                      params=[id_param("token_id", "Token id")],
                      responses={**_resp("Revoked"), **_errors("403", "404")}),
    }

    # --- Items ---
    item_filters = PAGINATION_PARAMS + [
        {"name": "type", "in": "query", "schema": {"type": "string", "enum": ["Lockbox", "Key", "Sign"]}},
        {"name": "status", "in": "query", "schema": {"type": "string", "enum": ["available", "checked_out", "assigned"]}},
        {"name": "q", "in": "query", "schema": S, "description": "Search custom id, label, address, location"},
        {"name": "property_id", "in": "query", "schema": I},
        {"name": "assigned_to", "in": "query", "schema": S},
    ]
    item_body = _obj({
        "type": {"type": "string", "enum": ["Lockbox", "Key", "Sign"]},
        "label": S, "custom_id": S, "location": S, "address": S, "assigned_to": S,
        "code_current": S, "code_previous": S, "supra_id": S,
        "key_hook_number": S, "keycode": S, "total_copies": I, "checkout_purpose": S, "master_key_id": I,
        "sign_subtype": {"type": "string", "enum": ["Piece", "Assembled Unit"]},
        "piece_type": S, "rider_text": S, "material": S, "condition": S,
        "property_id": I, "property_unit_id": I,
    })
    paths["/items"] = {
        "get": _op("List items", tag="Items", params=item_filters),
        "post": _op("Create an item", tag="Items",
                    description="'type' and 'label' are required. custom_id is auto-generated when omitted. "
                                "Only fields valid for the item's type are accepted.",
                    body={**item_body, "required": ["type", "label"]},
                    responses={**_resp("Created", "201"), **_errors("400", "409")}),
    }
    paths["/items/{item_ref}"] = {
        "get": _op("Get an item (includes active checkouts)", tag="Items", params=[item_ref],
                   responses={**_resp("OK"), **_errors("404")}),
        "patch": _op("Update an item", tag="Items", params=[item_ref], body=item_body,
                     responses={**_resp("Updated"), **_errors("400", "404", "409")}),
        "delete": _op("Delete an item (admin)", tag="Items", params=[item_ref],
                      responses={**_resp("Deleted"), **_errors("403", "404", "409")}),
    }
    paths["/items/{item_ref}/checkout"] = {
        "post": _op("Check out an item", tag="Items", params=[item_ref],
                    description="Keys: {copies, checked_out_to, purpose, expected_return_date, contact_id}. "
                                "Lockboxes: {code (required — rotates stored code), assigned_to, location, address}. "
                                "Signs: {purpose, assigned_to, location, address}.",
                    body=_obj({"copies": I, "checked_out_to": S, "purpose": S,
                               "expected_return_date": DATE, "contact_id": I,
                               "code": S, "assigned_to": S, "location": S, "address": S}),
                    responses={**_resp("Checked out"), **_resp("Checked out (key — returns checkout record)", "201"),
                               **_errors("400", "404", "409")}),
    }
    paths["/items/{item_ref}/checkin"] = {
        "post": _op("Check in an item", tag="Items", params=[item_ref],
                    description="Keys: provide {checkout_id} (preferred) or {copies}; assigned keys "
                                "check in fully when both are omitted. Lockboxes: {code required}. Signs: no body needed.",
                    body=_obj({"checkout_id": I, "copies": I, "code": S, "location": S, "address": S}),
                    responses={**_resp("Checked in"), **_errors("400", "404", "409")}),
    }
    paths["/items/{item_ref}/assign"] = {
        "post": _op("Assign an item", tag="Items", params=[item_ref],
                    description="Keys require 'assignment_type' (tenant|contractor|property) and consume copies. "
                                "Contractor assignments require expected_return_date. Property assignments "
                                "require property_id (assigned_to defaults to the property name).",
                    body=_obj({"assigned_to": S, "assignment_type": {"type": "string", "enum": ["tenant", "contractor", "property"]},
                               "copies": I, "expected_return_date": DATE, "property_id": I,
                               "property_unit_id": I, "contact_id": I, "location": S, "address": S}),
                    responses={**_resp("Assigned"), **_resp("Assigned (key — returns checkout record)", "201"),
                               **_errors("400", "404", "409")}),
    }

    # --- Checkouts ---
    paths["/checkouts"] = {
        "get": _op("List checkout/assignment history", tag="Checkouts",
                   params=PAGINATION_PARAMS + [
                       {"name": "active", "in": "query", "schema": B},
                       {"name": "overdue", "in": "query", "schema": B},
                       {"name": "item_id", "in": "query", "schema": I},
                       {"name": "contact_id", "in": "query", "schema": I},
                       {"name": "person", "in": "query", "schema": S},
                   ]),
    }
    paths["/checkouts/{checkout_id}"] = {
        "get": _op("Get a checkout record", tag="Checkouts",
                   params=[id_param("checkout_id", "Checkout id")],
                   responses={**_resp("OK"), **_errors("404")}),
    }

    # --- Properties ---
    prop_body = _obj({
        "name": S, "type": S, "address_line1": S, "address_line2": S, "city": S,
        "state": S, "postal_code": S, "country": S, "latitude": N, "longitude": N, "notes": S,
    })
    paths["/properties"] = {
        "get": _op("List properties", tag="Properties",
                   params=PAGINATION_PARAMS + [{"name": "q", "in": "query", "schema": S}]),
        "post": _op("Create a property", tag="Properties",
                    body={**prop_body, "required": ["name", "address_line1"]},
                    responses={**_resp("Created", "201"), **_errors("400")}),
    }
    paths["/properties/{property_id}"] = {
        "get": _op("Get a property (includes units and counts)", tag="Properties",
                   params=[id_param("property_id", "Property id")], responses={**_resp("OK"), **_errors("404")}),
        "patch": _op("Update a property", tag="Properties",
                     params=[id_param("property_id", "Property id")], body=prop_body,
                     responses={**_resp("Updated"), **_errors("400", "404")}),
        "delete": _op("Delete a property (admin)", tag="Properties",
                      params=[id_param("property_id", "Property id")],
                      responses={**_resp("Deleted"), **_errors("403", "404", "409")}),
    }
    unit_body = _obj({"label": S, "floor": S, "bedrooms": I, "bathrooms": N, "square_feet": I, "notes": S})
    paths["/properties/{property_id}/units"] = {
        "get": _op("List a property's units", tag="Properties", params=[id_param("property_id", "Property id")]),
        "post": _op("Add a unit to a property", tag="Properties",
                    params=[id_param("property_id", "Property id")],
                    body={**unit_body, "required": ["label"]},
                    responses={**_resp("Created", "201"), **_errors("400", "404")}),
    }
    paths["/units/{unit_id}"] = {
        "get": _op("Get a unit", tag="Properties", params=[id_param("unit_id", "Unit id")],
                   responses={**_resp("OK"), **_errors("404")}),
        "patch": _op("Update a unit", tag="Properties", params=[id_param("unit_id", "Unit id")], body=unit_body,
                     responses={**_resp("Updated"), **_errors("400", "404")}),
        "delete": _op("Delete a unit (admin)", tag="Properties", params=[id_param("unit_id", "Unit id")],
                      responses={**_resp("Deleted"), **_errors("403", "404", "409")}),
    }

    # --- Contacts ---
    contact_body = _obj({"contact_type": S, "name": S, "company": S, "email": S, "phone": S, "notes": S})
    paths["/contacts"] = {
        "get": _op("List contacts", tag="Contacts",
                   params=PAGINATION_PARAMS + [
                       {"name": "q", "in": "query", "schema": S},
                       {"name": "type", "in": "query", "schema": S},
                   ]),
        "post": _op("Create a contact", tag="Contacts",
                    body={**contact_body, "required": ["name"]},
                    responses={**_resp("Created", "201"), **_errors("400")}),
    }
    paths["/contacts/{contact_id}"] = {
        "get": _op("Get a contact (includes active checkouts)", tag="Contacts",
                   params=[id_param("contact_id", "Contact id")], responses={**_resp("OK"), **_errors("404")}),
        "patch": _op("Update a contact", tag="Contacts",
                     params=[id_param("contact_id", "Contact id")], body=contact_body,
                     responses={**_resp("Updated"), **_errors("400", "404")}),
        "delete": _op("Delete a contact (admin)", tag="Contacts",
                      params=[id_param("contact_id", "Contact id")],
                      responses={**_resp("Deleted"), **_errors("403", "404", "409")}),
    }

    # --- Smart locks ---
    lock_body = _obj({
        "label": S, "provider": S, "code": S, "backup_code": S, "instructions": S, "notes": S,
        "model_number": S, "serial_number": S, "pairing_code": S, "qr_code_data": S,
        "property_id": I, "property_unit_id": I,
    })
    paths["/smart-locks"] = {
        "get": _op("List smart locks", tag="Smart Locks",
                   params=PAGINATION_PARAMS + [
                       {"name": "q", "in": "query", "schema": S},
                       {"name": "property_id", "in": "query", "schema": I},
                   ]),
        "post": _op("Create a smart lock", tag="Smart Locks",
                    body={**lock_body, "required": ["label", "code"]},
                    responses={**_resp("Created", "201"), **_errors("400")}),
    }
    paths["/smart-locks/{lock_id}"] = {
        "get": _op("Get a smart lock (includes image metadata)", tag="Smart Locks",
                   params=[id_param("lock_id", "Smart lock id")], responses={**_resp("OK"), **_errors("404")}),
        "patch": _op("Update a smart lock", tag="Smart Locks",
                     params=[id_param("lock_id", "Smart lock id")], body=lock_body,
                     responses={**_resp("Updated"), **_errors("400", "404")}),
        "delete": _op("Delete a smart lock (admin)", tag="Smart Locks",
                      params=[id_param("lock_id", "Smart lock id")],
                      responses={**_resp("Deleted"), **_errors("403", "404")}),
    }

    # --- Audits ---
    paths["/audits"] = {
        "get": _op("List audits", tag="Audits",
                   params=PAGINATION_PARAMS + [{"name": "status", "in": "query",
                                                "schema": {"type": "string", "enum": ["pending", "in_progress", "completed"]}}]),
    }
    paths["/audits/{audit_id}"] = {
        "get": _op("Get an audit with its items and discrepancies", tag="Audits",
                   params=[id_param("audit_id", "Audit id")], responses={**_resp("OK"), **_errors("404")}),
    }

    # --- Admin ---
    user_body = _obj({"name": S, "email": S, "pin": S,
                      "role": {"type": "string", "enum": list(("admin", "owner", "user", "staff", "agent"))},
                      "is_active": B})
    paths["/users"] = {
        "get": _op("List account users (admin)", tag="Admin"),
        "post": _op("Create a user (admin)", tag="Admin",
                    body={**user_body, "required": ["name", "email", "pin"]},
                    responses={**_resp("Created", "201"), **_errors("400", "403", "409")}),
    }
    paths["/users/{user_id}"] = {
        "get": _op("Get a user (admin)", tag="Admin", params=[id_param("user_id", "User id")],
                   responses={**_resp("OK"), **_errors("403", "404")}),
        "patch": _op("Update a user (admin)", tag="Admin",
                     params=[id_param("user_id", "User id")], body=user_body,
                     responses={**_resp("Updated"), **_errors("400", "403", "404", "409")}),
        "delete": _op("Delete a user (admin)", tag="Admin", params=[id_param("user_id", "User id")],
                      responses={**_resp("Deleted"), **_errors("400", "403", "404")}),
    }
    paths["/settings"] = {
        "get": _op("Get tenant settings (admin)", tag="Admin"),
        "patch": _op("Update tenant settings (admin)", tag="Admin",
                     body=_obj({
                         "email_notifications_enabled": B, "notify_on_checkout": B,
                         "notify_on_checkin": B, "notify_on_overdue": B,
                         "overdue_grace_days": I, "low_keys_threshold": I,
                         "default_checkout_days": I, "receipt_header": S, "receipt_footer": S,
                     }),
                     responses={**_resp("Updated"), **_errors("400", "403")}),
    }
    paths["/activity-logs"] = {
        "get": _op("List activity logs (admin)", tag="Admin",
                   params=PAGINATION_PARAMS + [
                       {"name": "action", "in": "query", "schema": S},
                       {"name": "user_id", "in": "query", "schema": I},
                       {"name": "target_type", "in": "query", "schema": S},
                   ]),
    }
    paths["/stats"] = {
        "get": _op("Inventory summary: counts by type/status, active + overdue checkouts", tag="Admin"),
    }
    paths["/accounts"] = {
        "get": _op("List all tenant accounts (app admin, root domain)", tag="Admin",
                   responses={**_resp("OK"), **_errors("403")}),
    }

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "KBM API",
            "version": APP_VERSION,
            "description": (
                "REST API for KBM (keys, lockboxes, signs, properties, contacts, smart locks).\n\n"
                "**Base URL:** `https://<your-subdomain>.<domain>/api/v1` — tenant-scoped endpoints "
                "must be called on your company subdomain, exactly like the web app.\n\n"
                "**Authentication:** create a token with `POST /auth/tokens` using your login email "
                "and PIN, then send `Authorization: Bearer <token>` on every request. Tokens inherit "
                "your user's role; admin-only endpoints require an admin/owner token.\n\n"
                "**Pagination:** list endpoints accept `page` and `per_page` (max 100) and return a "
                "`pagination` object.\n\n"
                "**Errors:** all errors are JSON: `{\"error\": {\"code\": ..., \"message\": ...}}`."
            ),
        },
        "servers": [{"url": "/api/v1"}],
        "tags": [
            {"name": "Meta"}, {"name": "Auth"}, {"name": "Items"}, {"name": "Checkouts"},
            {"name": "Properties"}, {"name": "Contacts"}, {"name": "Smart Locks"},
            {"name": "Audits"}, {"name": "Admin"},
        ],
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "opaque"},
            },
        },
        "paths": paths,
    }
