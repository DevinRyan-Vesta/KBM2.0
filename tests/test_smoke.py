"""End-to-end smoke tests: every page renders, and the core office workflows
(create inventory, check out, check in, audit, export, receipts) work against
the real multi-tenant app.

Tests in this module share one app/tenant DB (session-scoped fixture) and are
ordered: the create tests run before the flows that use the records.
"""
import pytest

TENANT = {"Host": "acme.localhost"}
ROOT = {"Host": "localhost"}
ADMIN = {"Host": "admin.localhost"}

REDIRECT_OK = (200, 302)


def _row_id(table, column, value, extra=""):
    """Look up a tenant row id by a column value.

    Ids are not stable across the session-scoped DB (the API suite creates
    records first), so the workflow tests resolve ids from the labels/names
    they created rather than hard-coding them.
    """
    import os
    import sqlite3

    con = sqlite3.connect(os.path.join(os.getcwd(), "tenant_dbs", "acme.db"))
    try:
        row = con.execute(
            f"SELECT id FROM {table} WHERE {column} = ? {extra} ORDER BY id DESC LIMIT 1", (value,)
        ).fetchone()
    finally:
        con.close()
    assert row, f"no {table} row where {column} = {value!r}"
    return row[0]


def test_health(client):
    resp = client.get("/health", headers=ROOT)
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_root_domain_shows_landing_page(client):
    """Anonymous visit to the root domain must show the landing page, not a
    login redirect (regression: main.home used to shadow the landing route)."""
    resp = client.get("/", headers=ROOT)
    assert resp.status_code == 200


def test_tenant_home_requires_login(client):
    resp = client.get("/", headers=TENANT)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_unknown_subdomain_404s(client):
    resp = client.get("/", headers={"Host": "nosuch.localhost"})
    assert resp.status_code == 404


def test_checkout_api_on_root_domain_is_guarded(admin_client):
    """Regression: checkout APIs lacked @tenant_required and 500'd on the
    root domain. (The 404 handler bounces app admins to their dashboard,
    so a 302 is the authenticated equivalent of the 404 guard.)"""
    resp = admin_client.get("/checkout/api/items/search?q=x", headers=ROOT)
    assert resp.status_code in (302, 404)


class TestWorkflows:
    """Ordered end-to-end pass through the main office workflows."""

    def test_create_property_and_unit(self, tenant_client):
        resp = tenant_client.post("/properties/new", data={
            "name": "Maple Court",
            "type": "multi_family",
            "address_line1": "12 Maple St",
            "city": "Springfield",
            "state": "IL",
            "postal_code": "62704",
        }, headers=TENANT)
        assert resp.status_code in REDIRECT_OK
        prop_id = _row_id("properties", "name", "Maple Court")
        assert tenant_client.get(f"/properties/{prop_id}", headers=TENANT).status_code == 200
        resp = tenant_client.post(f"/properties/{prop_id}/units", data={"label": "Unit 1A"}, headers=TENANT)
        assert resp.status_code in REDIRECT_OK

    def test_create_contact(self, tenant_client):
        resp = tenant_client.post("/contacts/new", data={
            "name": "Jane Contractor",
            "contact_type": "contractor",
            "email": "jane@example.test",
            "phone": "555-0100",
        }, headers=TENANT)
        assert resp.status_code in REDIRECT_OK
        contact_id = _row_id("contacts", "name", "Jane Contractor")
        assert tenant_client.get(f"/contacts/{contact_id}", headers=TENANT).status_code == 200

    def test_create_inventory(self, tenant_client):
        assert tenant_client.post("/inventory/lockboxes/new", data={
            "label": "LB-001", "code": "1234", "location": "Office",
        }, headers=TENANT).status_code in REDIRECT_OK
        prop_id = _row_id("properties", "name", "Maple Court")
        assert tenant_client.post("/inventory/keys/new", data={
            "label": "KEY-001", "total_copies": "5",
            "key_hook_number": "H1", "property_id": str(prop_id),
        }, headers=TENANT).status_code in REDIRECT_OK
        assert tenant_client.post("/inventory/signs/new", data={
            "label": "SIGN-001", "sign_subtype": "Piece", "piece_type": "Frame",
            "material": "Metal", "condition": "Good",
        }, headers=TENANT).status_code in REDIRECT_OK

    def test_item_pages_render(self, tenant_client):
        for label in ("LB-001", "KEY-001", "SIGN-001"):
            item_id = _row_id("items", "label", label)
            assert tenant_client.get(f"/inventory/items/{item_id}", headers=TENANT).status_code == 200
        key_id = _row_id("items", "label", "KEY-001")
        assert tenant_client.get(f"/inventory/item/{key_id}/qrcode", headers=TENANT).status_code == 200
        assert tenant_client.get(f"/inventory/item/{key_id}/label", headers=TENANT).status_code == 200

    def test_key_checkout_and_receipt(self, tenant_client):
        from datetime import date, timedelta
        return_date = (date.today() + timedelta(days=7)).isoformat()
        key_id = _row_id("items", "label", "KEY-001")
        contact_id = _row_id("contacts", "name", "Jane Contractor")
        resp = tenant_client.post(f"/inventory/keys/{key_id}/checkout", data={
            "copies": "2",
            "checked_out_to": "Jane Contractor",
            "contact_id": str(contact_id),
            "purpose": "Showing",
            "expected_return_date": return_date,
        }, headers=TENANT)
        assert resp.status_code in REDIRECT_OK
        checkout_id = _row_id("item_checkouts", "item_id", key_id, extra="AND is_active = 1")
        assert tenant_client.get(f"/inventory/checkout/{checkout_id}/receipt", headers=TENANT).status_code == 200
        assert tenant_client.get("/inventory/receipts", headers=TENANT).status_code == 200

    def test_reports_and_exports_with_data(self, tenant_client):
        assert tenant_client.get("/reports", headers=TENANT).status_code == 200
        # These two used to crash (date - datetime TypeError) whenever a row
        # existed; the checkout above guarantees an upcoming-return row.
        resp = tenant_client.get("/exports/reports/upcoming-returns?format=csv", headers=TENANT)
        assert resp.status_code == 200
        assert resp.mimetype == "text/csv"
        resp = tenant_client.get("/exports/reports/checked-out-keys?format=csv", headers=TENANT)
        assert resp.status_code == 200
        # Lockbox item export used to be rejected by a rstrip('s') bug.
        resp = tenant_client.get("/exports/items/lockboxes?format=csv", headers=TENANT)
        assert resp.status_code == 200
        assert b"LB-001" in resp.data

    def test_empty_export_redirects_with_flash(self, tenant_client):
        resp = tenant_client.get("/exports/reports/overdue-returns?format=csv", headers=TENANT)
        assert resp.status_code == 302  # nothing overdue -> friendly redirect

    def test_key_checkin(self, tenant_client):
        key_id = _row_id("items", "label", "KEY-001")
        checkout_id = _row_id("item_checkouts", "item_id", key_id, extra="AND is_active = 1")
        resp = tenant_client.post(f"/inventory/keys/{key_id}/checkin", data={
            "copies": "2", "checkout_id": str(checkout_id),
        }, headers=TENANT)
        assert resp.status_code in REDIRECT_OK

    def test_audit_flow(self, tenant_client):
        assert tenant_client.post("/audits/create", data={}, headers=TENANT).status_code in REDIRECT_OK
        assert tenant_client.get("/audits/1", headers=TENANT).status_code == 200
        assert tenant_client.get("/audits/1/input", headers=TENANT).status_code == 200

    def test_search(self, tenant_client):
        assert tenant_client.get("/search?q=KEY", headers=TENANT).status_code == 200
        data = tenant_client.get("/search/suggest?q=KEY", headers=TENANT).get_json()
        assert any("KEY-001" in (r.get("label") or "") for r in data.get("results", []))


ALL_GET_PAGES = [
    "/", "/reports", "/search?q=test",
    "/inventory/lockboxes", "/inventory/keys", "/inventory/signs",
    "/inventory/lockboxes/new", "/inventory/keys/new", "/inventory/signs/new",
    "/inventory/signs/builder", "/inventory/receipts",
    "/checkout/", "/contacts/", "/contacts/new",
    "/properties/", "/properties/new", "/smart-locks/", "/smart-locks/new",
    "/audits/", "/audits/low-copy-report", "/audits/reorganize",
    "/auth/users", "/auth/users/new", "/auth/profile", "/auth/activity-logs",
    "/settings/",
]


@pytest.mark.parametrize("path", ALL_GET_PAGES)
def test_page_renders(tenant_client, path):
    resp = tenant_client.get(path, headers=TENANT)
    assert resp.status_code == 200, f"{path} -> {resp.status_code}"


ADMIN_PAGES = ["/admin/dashboard", "/admin/accounts", "/admin/app-admins", "/admin/system/updates"]


@pytest.mark.parametrize("path", ADMIN_PAGES)
def test_admin_page_renders(admin_client, path):
    resp = admin_client.get(path, headers=ADMIN)
    assert resp.status_code == 200, f"{path} -> {resp.status_code}"


@pytest.mark.parametrize("path", ADMIN_PAGES)
def test_admin_pages_blocked_for_tenant_user(tenant_client, path):
    resp = tenant_client.get(path, headers=ADMIN)
    assert resp.status_code in (302, 403)


# --- Host-based routing (apex / www / admin split) ---

def test_www_redirects_to_apex(client):
    resp = client.get("/some/path?x=1", headers={"Host": "www.localhost"})
    assert resp.status_code == 301
    assert "//localhost/some/path?x=1" in resp.headers["Location"]


def test_apex_login_redirects_to_admin_host(client):
    resp = client.get("/auth/login", headers=ROOT)
    assert resp.status_code == 301
    assert "admin.localhost/auth/login" in resp.headers["Location"]


def test_apex_admin_paths_redirect_to_admin_host(client):
    resp = client.get("/admin/dashboard", headers=ROOT)
    assert resp.status_code == 301
    assert "admin.localhost/admin/dashboard" in resp.headers["Location"]


def test_admin_host_root_redirects_to_login(client):
    resp = client.get("/", headers=ADMIN)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_admin_host_root_redirects_to_dashboard_when_authed(admin_client):
    resp = admin_client.get("/", headers=ADMIN)
    assert resp.status_code == 302
    assert "/admin/dashboard" in resp.headers["Location"]


def test_admin_login_page_renders(client):
    resp = client.get("/auth/login", headers=ADMIN)
    assert resp.status_code == 200


# --- Landing page subscribe ---

def test_landing_page_has_subscribe_form(client):
    resp = client.get("/", headers=ROOT)
    assert resp.status_code == 200
    assert b"/subscribe" in resp.data


def test_subscribe_stores_email(client, app):
    resp = client.post("/subscribe", data={"email": "lead@example.com"}, headers=ROOT)
    assert resp.status_code == 302
    assert "subscribed=1" in resp.headers["Location"]
    from utilities.master_database import LandingSubscriber
    with app.app_context():
        assert LandingSubscriber.query.filter_by(email="lead@example.com").count() == 1
    # Duplicate is silently accepted, not double-stored
    client.post("/subscribe", data={"email": "lead@example.com"}, headers=ROOT)
    with app.app_context():
        assert LandingSubscriber.query.filter_by(email="lead@example.com").count() == 1


def test_subscribe_rejects_bad_email(client):
    resp = client.post("/subscribe", data={"email": "not-an-email"}, headers=ROOT)
    assert resp.status_code == 302
    assert "subscribed=0" in resp.headers["Location"]


def test_subscribe_honeypot_swallows_bots(client, app):
    resp = client.post(
        "/subscribe",
        data={"email": "bot@example.com", "website": "http://spam"},
        headers=ROOT,
    )
    assert resp.status_code == 302
    from utilities.master_database import LandingSubscriber
    with app.app_context():
        assert LandingSubscriber.query.filter_by(email="bot@example.com").count() == 0


def test_subscribe_not_available_on_tenant(client):
    resp = client.post("/subscribe", data={"email": "x@example.com"}, headers=TENANT)
    assert resp.status_code == 404


def test_subscribers_page_renders_for_admin(admin_client):
    resp = admin_client.get("/admin/subscribers", headers=ADMIN)
    assert resp.status_code == 200


# --- Reserved subdomains ---

@pytest.mark.parametrize("name", ["www", "admin", "smtp", "mail", "api", "status", "billing"])
def test_reserved_subdomains_rejected_at_signup(app, name):
    from utilities.master_database import Account
    with app.app_context():
        ok, msg = Account.validate_subdomain(name)
    assert not ok
    assert "reserved" in msg


# --- Help Center ---

def test_help_index_renders(tenant_client):
    resp = tenant_client.get("/help/", headers=TENANT)
    assert resp.status_code == 200
    assert b"Help Center" in resp.data


def test_all_help_topics_render(tenant_client):
    from helpcenter import HELP_TOPICS
    for slug in HELP_TOPICS:
        resp = tenant_client.get(f"/help/{slug}", headers=TENANT)
        assert resp.status_code == 200, f"/help/{slug} -> {resp.status_code}"


def test_unknown_help_topic_404s(tenant_client):
    assert tenant_client.get("/help/no-such-topic", headers=TENANT).status_code == 404


def test_help_requires_login(client):
    resp = client.get("/help/", headers=TENANT)
    assert resp.status_code == 302


def test_context_sensitive_help_mapping():
    from helpcenter import topic_for_endpoint
    assert topic_for_endpoint("inventory.list_keys") == "keys"
    assert topic_for_endpoint("inventory.list_lockboxes") == "lockboxes"
    assert topic_for_endpoint("inventory.import_keys_upload") == "imports"
    assert topic_for_endpoint("checkout.start") == "checkout"
    assert topic_for_endpoint("audits.list_audits") == "audits"
    assert topic_for_endpoint("main.reports") == "reports"
    assert topic_for_endpoint("auth.list_users") == "users-roles"
    assert topic_for_endpoint("settings.settings_page") == "settings"
    assert topic_for_endpoint(None) is None


def test_help_button_present_on_pages(tenant_client):
    resp = tenant_client.get("/inventory/keys", headers=TENANT)
    assert b"/help/keys" in resp.data
    resp = tenant_client.get("/reports", headers=TENANT)
    assert b"/help/reports" in resp.data


# --- Property deletion (web UI) ---

def test_property_delete_flow(tenant_client):
    # Create a throwaway property
    resp = tenant_client.post("/properties/new", data={
        "name": "Smoke Delete Me",
        "type": "single_family",
        "address_line1": "1 Nowhere Ln",
    }, headers=TENANT)
    assert resp.status_code in REDIRECT_OK

    resp = tenant_client.get("/properties/api/search?q=Smoke Delete Me", headers=TENANT)
    matches = resp.get_json()
    assert matches, "created property not found"
    pid = matches[0]["id"]

    # Delete it
    resp = tenant_client.post(f"/properties/{pid}/delete", headers=TENANT)
    assert resp.status_code == 302

    resp = tenant_client.get("/properties/api/search?q=Smoke Delete Me", headers=TENANT)
    assert resp.get_json() == []


def test_property_delete_blocked_when_items_linked(tenant_client):
    # Property 1 (Maple Court) has keys/items linked from the workflow tests.
    resp = tenant_client.post("/properties/1/delete", headers=TENANT, follow_redirects=False)
    assert resp.status_code == 302  # bounced back with an error flash
    resp = tenant_client.get("/properties/api/search?q=Maple Court", headers=TENANT)
    assert resp.get_json(), "property with linked items must not be deleted"
