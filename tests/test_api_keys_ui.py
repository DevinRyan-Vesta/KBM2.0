"""Tests for the API Keys management page under Settings."""
import re

TENANT = {"Host": "acme.localhost"}


def _create_key(client, name="ui-test-key", expires="never"):
    return client.post("/settings/api-keys", data={"name": name, "expires": expires},
                       headers=TENANT, follow_redirects=True)


def test_page_requires_login(client):
    resp = client.get("/settings/api-keys", headers=TENANT)
    assert resp.status_code == 302  # bounced to login


def test_page_renders(tenant_client):
    resp = tenant_client.get("/settings/api-keys", headers=TENANT)
    assert resp.status_code == 200
    assert b"API Keys" in resp.data
    assert b"Create API Key" in resp.data


def test_create_shows_token_once(tenant_client):
    resp = _create_key(tenant_client, name="show-once")
    assert resp.status_code == 200
    # Raw token appears exactly once, right after creation...
    match = re.search(rb"kbm_[0-9a-f]{8}_[A-Za-z0-9_\-]+", resp.data)
    assert match, "raw token should be shown after creation"
    raw = match.group(0).decode()

    # ...and is gone on the next page load (only the masked prefix remains).
    resp2 = tenant_client.get("/settings/api-keys", headers=TENANT)
    assert raw.encode() not in resp2.data
    assert b"show-once" in resp2.data
    assert "kbm_{}_…".format(raw.split("_")[1]).encode() in resp2.data

    # The token actually works against the API.
    resp3 = tenant_client.get("/api/v1/me",
                              headers={**TENANT, "Authorization": f"Bearer {raw}"})
    assert resp3.status_code == 200


def test_create_with_expiry(tenant_client):
    resp = _create_key(tenant_client, name="expiring", expires="30")
    assert resp.status_code == 200
    resp = tenant_client.get("/settings/api-keys", headers=TENANT)
    assert b"expiring" in resp.data


def test_revoke_kills_token(app, tenant_client):
    resp = _create_key(tenant_client, name="to-revoke")
    raw = re.search(rb"kbm_[0-9a-f]{8}_[A-Za-z0-9_\-]+", resp.data).group(0).decode()

    from utilities.master_database import ApiToken
    with app.app_context():
        token = ApiToken.query.filter_by(token_prefix=raw.split("_")[1]).first()
        assert token is not None
        token_id = token.id

    resp = tenant_client.post(f"/settings/api-keys/{token_id}/revoke",
                              headers=TENANT, follow_redirects=True)
    assert resp.status_code == 200
    assert b"revoked" in resp.data.lower()

    # Token no longer authenticates.
    resp = tenant_client.get("/api/v1/me",
                             headers={**TENANT, "Authorization": f"Bearer {raw}"})
    assert resp.status_code == 401


def test_cannot_revoke_other_users_token_as_non_admin(app, tenant_client):
    """A regular user must not be able to revoke the admin's key."""
    from utilities.master_database import master_db, ApiToken, MasterUser, Account

    with app.app_context():
        account = Account.query.filter_by(subdomain="acme").first()
        regular = MasterUser.query.filter_by(email="regular@acme.test").first()
        if regular is None:
            regular = MasterUser(account_id=account.id, name="Regular User",
                                 email="regular@acme.test", role="user", is_active=True)
            regular.set_pin("2468")
            master_db.session.add(regular)
            master_db.session.commit()

    # Admin creates a key
    resp = _create_key(tenant_client, name="admins-key")
    raw = re.search(rb"kbm_[0-9a-f]{8}_[A-Za-z0-9_\-]+", resp.data).group(0).decode()
    with app.app_context():
        admin_token = ApiToken.query.filter_by(token_prefix=raw.split("_")[1]).first()
        admin_token_id = admin_token.id

    # Regular user logs in and tries to revoke it
    c = app.test_client()
    login = c.post("/auth/login", data={"pin": "2468"}, headers=TENANT)
    assert login.status_code == 302
    resp = c.post(f"/settings/api-keys/{admin_token_id}/revoke", headers=TENANT)
    assert resp.status_code == 404

    # And doesn't see it in their list
    resp = c.get("/settings/api-keys", headers=TENANT)
    assert b"admins-key" not in resp.data

    # Admin's key still works
    resp = c.get("/api/v1/me", headers={**TENANT, "Authorization": f"Bearer {raw}"})
    assert resp.status_code == 200
