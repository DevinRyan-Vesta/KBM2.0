"""REST API v1 tests.

Exercises the token lifecycle and every resource family end-to-end through
the real app factory, on the tenant subdomain, exactly like a real client.
"""
import pytest

TENANT_HOST = "acme.localhost"
ROOT_HOST = "localhost"
ADMIN_EMAIL = "admin@acme.test"
ADMIN_PIN = "9999"


@pytest.fixture(scope="module")
def api(app):
    """Anonymous client + helper that talks to the tenant subdomain."""
    return app.test_client()


@pytest.fixture(scope="module")
def token(api):
    """A real admin API token created through the public endpoint."""
    resp = api.post(
        "/api/v1/auth/tokens",
        json={"email": ADMIN_EMAIL, "pin": ADMIN_PIN, "name": "pytest"},
        headers={"Host": TENANT_HOST},
    )
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["token"].startswith("kbm_")
    return body["token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Host": TENANT_HOST, "Authorization": f"Bearer {token}"}


# --- Auth / tokens -------------------------------------------------------------

def test_index_is_public(api):
    resp = api.get("/api/v1/", headers={"Host": TENANT_HOST})
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "KBM API"


def test_openapi_and_docs(api):
    resp = api.get("/api/v1/openapi.json", headers={"Host": TENANT_HOST})
    assert resp.status_code == 200
    assert resp.get_json()["openapi"].startswith("3.0")
    resp = api.get("/api/v1/docs", headers={"Host": TENANT_HOST})
    assert resp.status_code == 200
    assert b"KBM API" in resp.data


def test_token_rejects_bad_credentials(api):
    resp = api.post(
        "/api/v1/auth/tokens",
        json={"email": ADMIN_EMAIL, "pin": "wrong"},
        headers={"Host": TENANT_HOST},
    )
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "invalid_credentials"


def test_missing_token_is_401(api):
    resp = api.get("/api/v1/items", headers={"Host": TENANT_HOST})
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "missing_token"


def test_garbage_token_is_401(api):
    resp = api.get(
        "/api/v1/items",
        headers={"Host": TENANT_HOST, "Authorization": "Bearer kbm_deadbeef_nope"},
    )
    assert resp.status_code == 401


def test_me(api, auth):
    resp = api.get("/api/v1/me", headers=auth)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["user"]["email"] == ADMIN_EMAIL
    assert body["token"]["name"] == "pytest"


def test_tenant_endpoint_requires_subdomain(api, token):
    resp = api.get(
        "/api/v1/items",
        headers={"Host": ROOT_HOST, "Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
    assert resp.get_json()["error"]["code"] == "tenant_required"


def test_token_list_and_revoke(api, auth):
    # Mint a disposable token and revoke it.
    resp = api.post(
        "/api/v1/auth/tokens",
        json={"email": ADMIN_EMAIL, "pin": ADMIN_PIN, "name": "disposable"},
        headers={"Host": TENANT_HOST},
    )
    disposable = resp.get_json()

    resp = api.get("/api/v1/auth/tokens", headers=auth)
    assert resp.status_code == 200
    names = [t["name"] for t in resp.get_json()["tokens"]]
    assert "disposable" in names

    resp = api.delete(f"/api/v1/auth/tokens/{disposable['id']}", headers=auth)
    assert resp.status_code == 200

    # The revoked token no longer authenticates.
    resp = api.get(
        "/api/v1/items",
        headers={"Host": TENANT_HOST, "Authorization": f"Bearer {disposable['token']}"},
    )
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "token_revoked"


# --- Items: CRUD + key checkout lifecycle ---------------------------------------

def test_key_full_lifecycle(api, auth):
    # Create
    resp = api.post("/api/v1/items", json={
        "type": "Key", "label": "Front Door — 123 Main", "total_copies": 5,
        "key_hook_number": "H12", "keycode": "54321",
    }, headers=auth)
    assert resp.status_code == 201, resp.get_json()
    key = resp.get_json()
    assert key["custom_id"].startswith("K")
    assert key["status"] == "available"

    # Lookup by custom_id
    resp = api.get(f"/api/v1/items/{key['custom_id']}", headers=auth)
    assert resp.status_code == 200
    assert resp.get_json()["id"] == key["id"]

    # Patch
    resp = api.patch(f"/api/v1/items/{key['id']}", json={"location": "Key cabinet A"}, headers=auth)
    assert resp.status_code == 200
    assert resp.get_json()["location"] == "Key cabinet A"

    # Checkout 2 copies
    resp = api.post(f"/api/v1/items/{key['id']}/checkout", json={
        "copies": 2, "checked_out_to": "Jane Contractor", "purpose": "Showing",
        "expected_return_date": "2026-07-20",
    }, headers=auth)
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["item"]["copies_checked_out"] == 2
    assert body["item"]["status"] == "checked_out"
    checkout_id = body["checkout"]["id"]

    # Can't check out more than available
    resp = api.post(f"/api/v1/items/{key['id']}/checkout", json={"copies": 99}, headers=auth)
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "no_copies_available"

    # Checkouts listing shows it as active
    resp = api.get("/api/v1/checkouts?active=true", headers=auth)
    ids = [c["id"] for c in resp.get_json()["checkouts"]]
    assert checkout_id in ids

    # Check the specific checkout back in
    resp = api.post(f"/api/v1/items/{key['id']}/checkin", json={"checkout_id": checkout_id}, headers=auth)
    assert resp.status_code == 200
    item = resp.get_json()["item"]
    assert item["copies_checked_out"] == 0
    assert item["status"] == "available"

    # Deleting is admin-only and works when the key is available
    resp = api.delete(f"/api/v1/items/{key['id']}", headers=auth)
    assert resp.status_code == 200
    resp = api.get(f"/api/v1/items/{key['id']}", headers=auth)
    assert resp.status_code == 404


def test_lockbox_requires_code_and_rotates(api, auth):
    resp = api.post("/api/v1/items", json={
        "type": "Lockbox", "label": "LB Front", "code_current": "1111",
    }, headers=auth)
    assert resp.status_code == 201
    lb = resp.get_json()

    # No code -> 400
    resp = api.post(f"/api/v1/items/{lb['id']}/checkout", json={}, headers=auth)
    assert resp.status_code == 400

    # With code -> rotates
    resp = api.post(f"/api/v1/items/{lb['id']}/checkout", json={"code": "2222"}, headers=auth)
    assert resp.status_code == 200
    item = resp.get_json()["item"]
    assert item["code_previous"] == "1111"
    assert item["code_current"] == "2222"
    assert item["status"] == "checked_out"

    resp = api.post(f"/api/v1/items/{lb['id']}/checkin", json={"code": "3333"}, headers=auth)
    assert resp.status_code == 200
    item = resp.get_json()["item"]
    assert item["status"] == "available"
    assert item["code_current"] == "3333"


def test_sign_checkout_and_assign(api, auth):
    resp = api.post("/api/v1/items", json={
        "type": "Sign", "label": "For Sale — Colonial", "sign_subtype": "Piece", "piece_type": "Sign",
    }, headers=auth)
    assert resp.status_code == 201
    sign = resp.get_json()
    assert sign["custom_id"].startswith("S")

    resp = api.post(f"/api/v1/items/{sign['id']}/assign", json={
        "assigned_to": "Agent Bob", "assignment_type": "tenant",
    }, headers=auth)
    assert resp.status_code == 200
    assert resp.get_json()["item"]["status"] == "assigned"

    resp = api.post(f"/api/v1/items/{sign['id']}/checkin", json={}, headers=auth)
    assert resp.status_code == 200
    assert resp.get_json()["item"]["status"] == "available"


def test_item_type_validation(api, auth):
    resp = api.post("/api/v1/items", json={"type": "Spaceship", "label": "X"}, headers=auth)
    assert resp.status_code == 400

    # Key-only field rejected on a lockbox
    resp = api.post("/api/v1/items", json={
        "type": "Lockbox", "label": "LB2", "keycode": "12345",
    }, headers=auth)
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "unknown_fields"


def test_items_pagination_and_filters(api, auth):
    for i in range(3):
        api.post("/api/v1/items", json={"type": "Key", "label": f"PageKey {i}", "total_copies": 1}, headers=auth)

    resp = api.get("/api/v1/items?type=Key&per_page=2&page=1", headers=auth)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["items"]) <= 2
    assert body["pagination"]["per_page"] == 2
    assert body["pagination"]["total"] >= 3

    resp = api.get("/api/v1/items?q=PageKey", headers=auth)
    assert resp.get_json()["pagination"]["total"] == 3


# --- Properties, contacts, smart locks -------------------------------------------

def test_property_and_unit_crud(api, auth):
    resp = api.post("/api/v1/properties", json={
        "name": "Maple Apartments", "type": "multi_family",
        "address_line1": "12 Maple St", "city": "Springfield", "state": "IL",
    }, headers=auth)
    assert resp.status_code == 201, resp.get_json()
    prop = resp.get_json()

    resp = api.post(f"/api/v1/properties/{prop['id']}/units", json={
        "label": "Unit 2B", "bedrooms": 2, "bathrooms": 1.5,
    }, headers=auth)
    assert resp.status_code == 201
    unit = resp.get_json()

    resp = api.get(f"/api/v1/properties/{prop['id']}", headers=auth)
    body = resp.get_json()
    assert body["item_count"] == 0
    assert [u["label"] for u in body["units"]] == ["Unit 2B"]

    resp = api.patch(f"/api/v1/units/{unit['id']}", json={"floor": "2"}, headers=auth)
    assert resp.get_json()["floor"] == "2"

    # Assign a key to the property, then deletion is blocked
    resp = api.post("/api/v1/items", json={"type": "Key", "label": "Maple key", "total_copies": 2}, headers=auth)
    key = resp.get_json()
    resp = api.post(f"/api/v1/items/{key['id']}/assign", json={
        "assignment_type": "property", "property_id": prop["id"], "copies": 1,
    }, headers=auth)
    assert resp.status_code == 201, resp.get_json()
    assert resp.get_json()["item"]["assigned_to"] == "Maple Apartments"

    resp = api.delete(f"/api/v1/properties/{prop['id']}", headers=auth)
    assert resp.status_code == 409


def test_contact_crud_and_checkout_link(api, auth):
    resp = api.post("/api/v1/contacts", json={
        "name": "Carol Cleaner", "contact_type": "contractor", "email": "carol@clean.test",
    }, headers=auth)
    assert resp.status_code == 201
    contact = resp.get_json()

    resp = api.post("/api/v1/items", json={"type": "Key", "label": "Cleaner key", "total_copies": 3}, headers=auth)
    key = resp.get_json()
    resp = api.post(f"/api/v1/items/{key['id']}/checkout", json={
        "copies": 1, "contact_id": contact["id"],
    }, headers=auth)
    assert resp.status_code == 201

    resp = api.get(f"/api/v1/contacts/{contact['id']}", headers=auth)
    assert len(resp.get_json()["active_checkouts"]) == 1

    # Deleting a contact with active checkouts is blocked
    resp = api.delete(f"/api/v1/contacts/{contact['id']}", headers=auth)
    assert resp.status_code == 409


def test_smart_lock_crud(api, auth):
    resp = api.post("/api/v1/smart-locks", json={
        "label": "Front Door Encode", "provider": "Schlage", "code": "080808",
    }, headers=auth)
    assert resp.status_code == 201
    lock = resp.get_json()

    resp = api.patch(f"/api/v1/smart-locks/{lock['id']}", json={"backup_code": "424242"}, headers=auth)
    assert resp.get_json()["backup_code"] == "424242"

    resp = api.delete(f"/api/v1/smart-locks/{lock['id']}", headers=auth)
    assert resp.status_code == 200


# --- Admin --------------------------------------------------------------------

def test_user_management(api, auth):
    resp = api.post("/api/v1/users", json={
        "name": "API Staffer", "email": "staffer@acme.test", "pin": "13579", "role": "staff",
    }, headers=auth)
    assert resp.status_code == 201, resp.get_json()
    user = resp.get_json()

    # Non-admin token can't manage users
    resp = api.post("/api/v1/auth/tokens", json={"email": "staffer@acme.test", "pin": "13579"},
                    headers={"Host": TENANT_HOST})
    staff_token = resp.get_json()["token"]
    staff_auth = {"Host": TENANT_HOST, "Authorization": f"Bearer {staff_token}"}
    resp = api.get("/api/v1/users", headers=staff_auth)
    assert resp.status_code == 403
    # ...but can read inventory
    resp = api.get("/api/v1/items", headers=staff_auth)
    assert resp.status_code == 200

    resp = api.patch(f"/api/v1/users/{user['id']}", json={"is_active": False}, headers=auth)
    assert resp.get_json()["is_active"] is False

    # Deactivated user's token stops working
    resp = api.get("/api/v1/items", headers=staff_auth)
    assert resp.status_code == 401

    resp = api.delete(f"/api/v1/users/{user['id']}", headers=auth)
    assert resp.status_code == 200


def test_settings_roundtrip(api, auth):
    resp = api.get("/api/v1/settings", headers=auth)
    assert resp.status_code == 200

    resp = api.patch("/api/v1/settings", json={
        "low_keys_threshold": 6, "notify_on_overdue": False,
    }, headers=auth)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["low_keys_threshold"] == 6
    assert body["notify_on_overdue"] is False

    resp = api.patch("/api/v1/settings", json={"bogus_setting": 1}, headers=auth)
    assert resp.status_code == 400


def test_activity_logs_and_stats(api, auth):
    resp = api.get("/api/v1/activity-logs", headers=auth)
    assert resp.status_code == 200
    assert resp.get_json()["pagination"]["total"] > 0

    resp = api.get("/api/v1/stats", headers=auth)
    assert resp.status_code == 200
    body = resp.get_json()
    assert "Key" in body["items"]
    assert "active_checkouts" in body


def test_accounts_requires_app_admin(api, auth, app):
    # Tenant admin token -> 403
    resp = api.get("/api/v1/accounts",
                   headers={"Host": ROOT_HOST, "Authorization": auth["Authorization"]})
    assert resp.status_code == 403

    # App admin token on root domain -> 200
    resp = api.post("/api/v1/auth/tokens", json={"email": "root@kbm.test", "pin": "8888"},
                    headers={"Host": ROOT_HOST})
    assert resp.status_code == 201, resp.get_json()
    root_token = resp.get_json()["token"]
    resp = api.get("/api/v1/accounts",
                   headers={"Host": ROOT_HOST, "Authorization": f"Bearer {root_token}"})
    assert resp.status_code == 200
    subdomains = [a["subdomain"] for a in resp.get_json()["accounts"]]
    assert "acme" in subdomains

    # App admin token also works on tenant subdomains
    resp = api.get("/api/v1/items",
                   headers={"Host": TENANT_HOST, "Authorization": f"Bearer {root_token}"})
    assert resp.status_code == 200
