"""End-to-end smoke tests: every page renders, and the core office workflows
(create inventory, check out, check in, audit, export, receipts) work against
the real multi-tenant app.

Tests in this module share one app/tenant DB (session-scoped fixture) and are
ordered: the create tests run before the flows that use the records.
"""
import pytest

TENANT = {"Host": "acme.localhost"}
ROOT = {"Host": "localhost"}

REDIRECT_OK = (200, 302)


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
        assert tenant_client.get("/properties/1", headers=TENANT).status_code == 200
        resp = tenant_client.post("/properties/1/units", data={"label": "Unit 1A"}, headers=TENANT)
        assert resp.status_code in REDIRECT_OK

    def test_create_contact(self, tenant_client):
        resp = tenant_client.post("/contacts/new", data={
            "name": "Jane Contractor",
            "contact_type": "contractor",
            "email": "jane@example.test",
            "phone": "555-0100",
        }, headers=TENANT)
        assert resp.status_code in REDIRECT_OK
        assert tenant_client.get("/contacts/1", headers=TENANT).status_code == 200

    def test_create_inventory(self, tenant_client):
        assert tenant_client.post("/inventory/lockboxes/new", data={
            "label": "LB-001", "code": "1234", "location": "Office",
        }, headers=TENANT).status_code in REDIRECT_OK
        assert tenant_client.post("/inventory/keys/new", data={
            "label": "KEY-001", "total_copies": "5",
            "key_hook_number": "H1", "property_id": "1",
        }, headers=TENANT).status_code in REDIRECT_OK
        assert tenant_client.post("/inventory/signs/new", data={
            "label": "SIGN-001", "sign_subtype": "Piece", "piece_type": "Frame",
            "material": "Metal", "condition": "Good",
        }, headers=TENANT).status_code in REDIRECT_OK

    def test_item_pages_render(self, tenant_client):
        for item_id in (1, 2, 3):
            assert tenant_client.get(f"/inventory/items/{item_id}", headers=TENANT).status_code == 200
        assert tenant_client.get("/inventory/item/2/qrcode", headers=TENANT).status_code == 200
        assert tenant_client.get("/inventory/item/2/label", headers=TENANT).status_code == 200

    def test_key_checkout_and_receipt(self, tenant_client):
        from datetime import date, timedelta
        return_date = (date.today() + timedelta(days=7)).isoformat()
        resp = tenant_client.post("/inventory/keys/2/checkout", data={
            "copies": "2",
            "checked_out_to": "Jane Contractor",
            "contact_id": "1",
            "purpose": "Showing",
            "expected_return_date": return_date,
        }, headers=TENANT)
        assert resp.status_code in REDIRECT_OK
        assert tenant_client.get("/inventory/checkout/1/receipt", headers=TENANT).status_code == 200
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
        resp = tenant_client.post("/inventory/keys/2/checkin", data={
            "copies": "2", "checkout_id": "1",
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
    resp = admin_client.get(path, headers=ROOT)
    assert resp.status_code == 200, f"{path} -> {resp.status_code}"


@pytest.mark.parametrize("path", ADMIN_PAGES)
def test_admin_pages_blocked_for_tenant_user(tenant_client, path):
    resp = tenant_client.get(path, headers=ROOT)
    assert resp.status_code in (302, 403)


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
