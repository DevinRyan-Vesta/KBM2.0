"""
Send overdue-item reminder emails across all active tenants.

Run from inside the python-app container:

    docker compose exec python-app python -m utilities.send_overdue_reminders

Wire to host cron for a daily run (see EMAIL_SETUP.md).

Idempotent in the sense that it can be re-run safely, but does NOT throttle:
each invocation will send one reminder per still-overdue active checkout per
tenant. So run it at most once per day. (Throttling per checkout could be
added later via a `last_overdue_reminder_sent_at` column on ItemCheckout.)
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime

# Make sure we can import the app when run as a module from /app
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import timedelta  # noqa: E402

from app_multitenant import create_app  # noqa: E402
from utilities.master_database import Account  # noqa: E402
from utilities.tenant_manager import tenant_manager  # noqa: E402
from utilities.tenant_helpers import tenant_query  # noqa: E402
from utilities.database import ItemCheckout, get_tenant_settings  # noqa: E402
from utilities.email import is_configured, notify_overdue  # noqa: E402

log = logging.getLogger("kbm.overdue")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def run_for_tenant(account: Account) -> tuple[int, int]:
    """Return (sent_count, overdue_count) for the given tenant."""
    sent = 0
    overdue_total = 0
    now = datetime.utcnow()

    # Switch the tenant context the same way the request middleware does.
    # set_tenant_context relies on flask.g, which exists inside an app context.
    try:
        tenant_manager.set_tenant_context(account)
    except FileNotFoundError:
        log.warning("Skipping %s: tenant DB file missing", account.subdomain)
        return 0, 0

    # Apply the tenant's overdue grace period so we don't pester people the
    # day after their expected return. Default 0 = remind starting day after.
    grace_days = max(0, get_tenant_settings().overdue_grace_days or 0)
    cutoff = now - timedelta(days=grace_days)

    overdue = (
        tenant_query(ItemCheckout)
        .filter(
            ItemCheckout.is_active.is_(True),
            ItemCheckout.expected_return_date.isnot(None),
            ItemCheckout.expected_return_date < cutoff,
        )
        .all()
    )

    overdue_total = len(overdue)
    for checkout in overdue:
        if not checkout.item:
            continue
        days = max(1, (now - checkout.expected_return_date).days)
        ok = notify_overdue(
            checkout,
            days_overdue=days,
            tenant_name=account.company_name or account.subdomain,
        )
        if ok:
            sent += 1

    tenant_manager.close_tenant_session()
    return sent, overdue_total


def main() -> int:
    if not is_configured():
        log.error("SMTP is not configured (SMTP_HOST / SMTP_FROM unset). Aborting.")
        return 2

    app = create_app()
    grand_sent = 0
    grand_overdue = 0
    grand_tenants = 0

    with app.app_context():
        accounts = Account.query.filter_by(status="active").all()
        log.info("Scanning %d active tenant(s) for overdue items", len(accounts))

        for account in accounts:
            grand_tenants += 1
            try:
                sent, overdue = run_for_tenant(account)
            except Exception:
                log.exception("Failed processing tenant %s", account.subdomain)
                continue

            log.info(
                "%s: %d overdue item(s), %d email(s) sent",
                account.subdomain, overdue, sent,
            )
            grand_sent += sent
            grand_overdue += overdue

    log.info(
        "Done. Tenants scanned: %d. Overdue items: %d. Emails sent: %d.",
        grand_tenants, grand_overdue, grand_sent,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
