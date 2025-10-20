import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app import create_app
from utilities.database import db, Item, User


@pytest.fixture
def app():
    db_name = f"test_{uuid4().hex}.db"
    os.environ["ENV"] = "testing"
    os.environ["DATABASE_URI"] = f"sqlite:///{db_name}"

    application = create_app()
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()

    db_path = Path.home() / "KBM2_data" / db_name
    if db_path.exists():
        db_path.unlink()

    os.environ.pop("DATABASE_URI", None)
    os.environ.pop("ENV", None)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_user(app):
    with app.app_context():
        user = User(name="Test Admin", email="admin@example.com", role="admin")
        user.set_pin("1234")
        db.session.add(user)
        db.session.commit()
        return SimpleNamespace(id=user.id)


@pytest.fixture
def auth_client(client, app, admin_user):
    response = client.post("/auth/login", data={"pin": "1234"}, follow_redirects=True)
    assert response.status_code == 200
    return client


@pytest.fixture
def sample_lockbox(app, admin_user):
    with app.app_context():
        user = db.session.get(User, admin_user.id)
        custom_id = Item.generate_custom_id("Lockbox")
        item = Item(
            type="Lockbox",
            custom_id=custom_id,
            label="LB-Alpha",
            location="Main Office",
            status="available",
            code_current="4321",
        )
        if user is not None:
            item.record_action("created", user)
        db.session.add(item)
        db.session.commit()
        return SimpleNamespace(id=item.id, custom_id=item.custom_id, label=item.label)
