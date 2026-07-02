"""Pagination behavior on large lists.

Named test_zz_* so it runs AFTER test_smoke.py — it bulk-inserts rows into
the shared session-scoped tenant DB, which would upset the smoke tests'
assumptions about record ids if it ran first.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TENANT = {"Host": "acme.localhost"}


def _seed_keys(app, n=60):
    from utilities.tenant_manager import tenant_manager
    from utilities.database import Item, utc_now
    from sqlalchemy.orm import Session

    engine = tenant_manager.get_tenant_engine("acme")
    with Session(engine) as s:
        existing = s.query(Item).filter_by(type="Key").count()
        for i in range(n):
            s.add(Item(
                type="Key",
                custom_id=f"KP{i:04d}",
                label=f"Bulk Key {i:04d}",
                total_copies=3,
                copies_checked_out=0,
                status="available",
                last_action="created",
                last_action_at=utc_now(),
            ))
        s.commit()
        total = s.query(Item).filter_by(type="Key").count()
    return existing, total


def test_keys_list_paginates_beyond_50(app, tenant_client):
    _, total = _seed_keys(app, 60)
    assert total > 50

    resp = tenant_client.get("/inventory/keys", headers=TENANT)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "pagination-bar" in body
    assert f"of {total}" in body
    # newest first: the bulk keys appear on page 1
    assert "Bulk Key" in body

    resp2 = tenant_client.get("/inventory/keys?page=2", headers=TENANT)
    assert resp2.status_code == 200
    assert "pagination-bar" in resp2.get_data(as_text=True)

    # page-1 rows and page-2 rows don't overlap
    ids1 = set(part.split("<")[0] for part in body.split("KP")[1:])
    body2 = resp2.get_data(as_text=True)
    ids2 = set(part.split("<")[0] for part in body2.split("KP")[1:])
    assert not (ids1 & ids2 - {""})


def test_page_out_of_range_clamps(tenant_client):
    resp = tenant_client.get("/inventory/keys?page=99999", headers=TENANT)
    assert resp.status_code == 200


def test_per_page_is_capped(tenant_client):
    resp = tenant_client.get("/inventory/keys?per_page=100000", headers=TENANT)
    assert resp.status_code == 200


def test_garbage_page_params_dont_500(tenant_client):
    resp = tenant_client.get("/inventory/keys?page=banana&per_page=-3", headers=TENANT)
    assert resp.status_code == 200


def test_pagination_preserves_search_query(tenant_client):
    resp = tenant_client.get("/inventory/keys?q=Bulk&per_page=10&page=2", headers=TENANT)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "q=Bulk" in body  # prev/next links keep the search term


def test_signs_and_lockboxes_small_lists_hide_bar(tenant_client):
    for path in ("/inventory/signs", "/inventory/lockboxes"):
        resp = tenant_client.get(path, headers=TENANT)
        assert resp.status_code == 200
        assert "pagination-bar" not in resp.get_data(as_text=True)


def test_calendar_renders_and_navigates(tenant_client):
    resp = tenant_client.get("/calendar/", headers=TENANT)
    assert resp.status_code == 200
    resp = tenant_client.get("/calendar/?year=2026&month=12", headers=TENANT)
    assert resp.status_code == 200
    # Invalid month redirects to the current month instead of erroring
    resp = tenant_client.get("/calendar/?year=2026&month=13", headers=TENANT)
    assert resp.status_code == 302


def test_dashboard_charts_render(tenant_client):
    resp = tenant_client.get("/", headers=TENANT)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Checkouts per Week" in body
    assert "Inventory by Status" in body


def test_notification_bell_renders(tenant_client):
    resp = tenant_client.get("/", headers=TENANT)
    assert b"notify-bell" in resp.data
