"""Pytest fixtures for the multi-tenant KBM app.

Boots the real production app factory (app_multitenant.create_app) against a
temp directory, provisions one tenant account ("acme") with an admin user,
and exposes logged-in test clients. Tenant routing is exercised the same way
production works: via the Host header (acme.localhost vs localhost).
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TENANT_HOST = "acme.localhost"
ROOT_HOST = "localhost"
TENANT_PIN = "9999"
APP_ADMIN_PIN = "8888"


@pytest.fixture(scope="session")
def app():
    workdir = tempfile.mkdtemp(prefix="kbm-tests-")
    old_cwd = os.getcwd()
    os.chdir(workdir)  # master_db/ and tenant_dbs/ are created relative to cwd

    os.environ["ENV"] = "testing"
    os.environ["SERVER_NAME"] = "localhost"
    os.environ["BASE_DOMAIN"] = "localhost"
    os.environ["AUTO_CREATE_SCHEMA"] = "true"
    os.environ["RATELIMIT_ENABLED"] = "false"

    from app_multitenant import create_app

    application = create_app()
    application.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SERVER_NAME=None,  # let the test client set Host per request
    )

    from utilities.master_database import master_db, Account, MasterUser
    from utilities.tenant_manager import tenant_manager

    with application.app_context():
        master_db.create_all()
        account = Account(
            subdomain="acme",
            company_name="Acme Test Co",
            status="active",
            database_path="tenant_dbs/acme.db",
        )
        master_db.session.add(account)
        master_db.session.commit()
        tenant_manager.create_tenant_database(account)

        admin = MasterUser(
            account_id=account.id,
            name="Test Admin",
            email="admin@acme.test",
            role="admin",
            is_active=True,
        )
        admin.set_pin(TENANT_PIN)
        app_admin = MasterUser(
            account_id=None,
            name="App Admin",
            email="root@kbm.test",
            role="app_admin",
            is_active=True,
        )
        app_admin.set_pin(APP_ADMIN_PIN)
        master_db.session.add_all([admin, app_admin])
        master_db.session.commit()

    yield application

    os.chdir(old_cwd)
    shutil.rmtree(workdir, ignore_errors=True)


@pytest.fixture
def client(app):
    """Anonymous client (no session)."""
    return app.test_client()


@pytest.fixture
def tenant_client(app):
    """Client logged in as the tenant admin, on the tenant subdomain."""
    c = app.test_client()
    resp = c.post(
        "/auth/login",
        data={"pin": TENANT_PIN},
        headers={"Host": TENANT_HOST},
    )
    assert resp.status_code == 302
    return c


@pytest.fixture
def admin_client(app):
    """Client logged in as the app admin, on the root domain."""
    c = app.test_client()
    resp = c.post(
        "/auth/login",
        data={"pin": APP_ADMIN_PIN},
        headers={"Host": ROOT_HOST},
    )
    assert resp.status_code == 302
    return c
