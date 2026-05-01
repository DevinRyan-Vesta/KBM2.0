"""
Generic SMTP email helper used by checkout/checkin/overdue notifications.

Reads SMTP config from environment variables. If SMTP_HOST is empty, all sends
are silently skipped (returning False) — that way the rest of the app keeps
working in development or before the operator configures a provider.

Templates live under templates/emails/<name>.txt and templates/emails/<name>.html
and are rendered with Jinja using the app's normal template loader.
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from flask import current_app, render_template

log = logging.getLogger(__name__)


def _bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def is_configured() -> bool:
    """True if enough SMTP config is present to attempt a send."""
    return bool(os.getenv("SMTP_HOST", "").strip()) and bool(os.getenv("SMTP_FROM", "").strip())


def send_email(
    to: str | list[str],
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
    reply_to: Optional[str] = None,
) -> bool:
    """Send a single email via SMTP. Returns True on success.

    Returns False (and logs) on any failure or when SMTP isn't configured —
    callers should not raise for email failures, since email is supplementary
    to the operation that triggered it.
    """
    if not is_configured():
        log.info("Email skipped (SMTP not configured): subject=%r to=%r", subject, to)
        return False

    if isinstance(to, str):
        recipients = [to.strip()] if to.strip() else []
    else:
        recipients = [r.strip() for r in to if r and r.strip()]

    if not recipients:
        log.info("Email skipped (no recipients): subject=%r", subject)
        return False

    host = os.environ["SMTP_HOST"].strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "").strip() or None
    password = os.getenv("SMTP_PASSWORD", "")
    use_ssl = _bool("SMTP_USE_SSL", False)
    use_starttls = _bool("SMTP_USE_STARTTLS", True) and not use_ssl
    from_addr = os.environ["SMTP_FROM"].strip()
    from_name = os.getenv("SMTP_FROM_NAME", "").strip() or None

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_addr}>" if from_name else from_addr
    msg["To"] = ", ".join(recipients)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    try:
        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as smtp:
                if username:
                    smtp.login(username, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as smtp:
                smtp.ehlo()
                if use_starttls:
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                if username:
                    smtp.login(username, password)
                smtp.send_message(msg)
    except Exception:
        log.exception("Email send failed: subject=%r to=%r", subject, recipients)
        return False

    log.info("Email sent: subject=%r to=%r", subject, recipients)
    return True


def send_template_email(
    to: str | list[str],
    template_name: str,
    subject: str,
    **context,
) -> bool:
    """Render `templates/emails/<template_name>.txt` (and optionally `.html`),
    then send. Context is passed verbatim to both templates.

    Must be called inside a Flask app context (for render_template).
    """
    text_body = render_template(f"emails/{template_name}.txt", **context)

    html_body: Optional[str] = None
    try:
        html_body = render_template(f"emails/{template_name}.html", **context)
    except Exception:
        # HTML template is optional — text-only is fine.
        pass

    return send_email(to=to, subject=subject, text_body=text_body, html_body=html_body)


def lookup_contact_email(name: str) -> Optional[str]:
    """Find an active contact by case-insensitive name match and return their
    email if any. Returns None if not found, no email on file, or `name` is
    blank. Safe to call from any tenant request.
    """
    if not name or not name.strip():
        return None

    from utilities.tenant_helpers import tenant_query
    from utilities.database import Contact

    try:
        contact = tenant_query(Contact).filter(Contact.name.ilike(name.strip())).first()
    except Exception:
        log.exception("Contact lookup failed for name=%r", name)
        return None

    if not contact or not contact.email:
        return None

    return contact.email.strip() or None


def tenant_app_url(subdomain: str, path: str = "/") -> str:
    """Build a public URL for a given tenant + path, using BASE_DOMAIN and
    APP_URL_SCHEME from config/env. Used in email links."""
    base = (os.getenv("BASE_DOMAIN", "") or "").strip().split(":")[0] or "localhost"
    scheme = os.getenv("APP_URL_SCHEME", "https").strip() or "https"
    if not path.startswith("/"):
        path = "/" + path
    return f"{scheme}://{subdomain}.{base}{path}"


def _current_tenant_name() -> Optional[str]:
    """Return the current tenant's company name if available."""
    try:
        from utilities.tenant_manager import tenant_manager
        tenant = tenant_manager.get_current_tenant()
        if tenant:
            return getattr(tenant, "company_name", None) or getattr(tenant, "subdomain", None)
    except Exception:
        pass
    return None


def _resolve_recipient_email(checkout) -> Optional[str]:
    """Find the email address to notify for a given ItemCheckout.

    Prefers the directly-linked Contact (set when the recipient was picked
    from the autocomplete). Falls back to a case-insensitive Contact-name
    lookup for legacy checkouts that don't have contact_id set.
    """
    contact = getattr(checkout, "contact", None)
    if contact is not None and contact.email and contact.email.strip():
        return contact.email.strip()
    return lookup_contact_email(getattr(checkout, "checked_out_to", "") or "")


def _tenant_emails_enabled(event: Optional[str] = None) -> bool:
    """Check the current tenant's settings to see if email notifications
    are turned on, optionally for a specific event ('checkout' / 'checkin'
    / 'overdue').

    Both the master switch (`email_notifications_enabled`) AND the per-event
    flag (`notify_on_<event>`) must be true to send. Defaults to True on any
    error so a settings-table problem doesn't silently kill emails."""
    try:
        from utilities.database import get_tenant_settings
        settings = get_tenant_settings()
        if not settings.email_notifications_enabled:
            return False
        if event == "checkout":
            return bool(settings.notify_on_checkout)
        if event == "checkin":
            return bool(settings.notify_on_checkin)
        if event == "overdue":
            return bool(settings.notify_on_overdue)
        return True
    except Exception:
        return True


def notify_checkout(checkout, *, tenant_name: Optional[str] = None) -> bool:
    """Send a 'you've been issued an item' email for the given ItemCheckout."""
    if not is_configured():
        return False
    if not _tenant_emails_enabled("checkout"):
        return False
    item = checkout.item
    if item is None:
        return False
    email = _resolve_recipient_email(checkout)
    if not email:
        return False
    try:
        return send_template_email(
            to=email,
            template_name="checkout",
            subject=f"Item issued: {item.label}",
            recipient_name=checkout.checked_out_to or "",
            tenant_name=tenant_name or _current_tenant_name(),
            item_label=item.label,
            item_custom_id=item.custom_id,
            item_type=item.type,
            item_address=item.address,
            quantity=checkout.quantity or 1,
            purpose=checkout.purpose,
            expected_return_date=checkout.expected_return_date,
            checkout_id=checkout.id,
        )
    except Exception:
        log.exception("notify_checkout failed for checkout=%r", checkout.id)
        return False


def notify_checkin(checkout, *, tenant_name: Optional[str] = None) -> bool:
    """Send a 'return confirmed' email for the given ItemCheckout."""
    if not is_configured():
        return False
    if not _tenant_emails_enabled("checkin"):
        return False
    item = checkout.item
    if item is None:
        return False
    email = _resolve_recipient_email(checkout)
    if not email:
        return False
    try:
        return send_template_email(
            to=email,
            template_name="checkin",
            subject=f"Return confirmed: {item.label}",
            recipient_name=checkout.checked_out_to or "",
            tenant_name=tenant_name or _current_tenant_name(),
            item_label=item.label,
            item_custom_id=item.custom_id,
            item_type=item.type,
            quantity=checkout.quantity or 1,
            checked_in_at=checkout.checked_in_at,
            checkout_id=checkout.id,
        )
    except Exception:
        log.exception("notify_checkin failed for checkout=%r", checkout.id)
        return False


def notify_overdue(checkout, days_overdue: int, *, tenant_name: Optional[str] = None) -> bool:
    """Send an 'item is overdue' reminder for the given ItemCheckout."""
    if not is_configured():
        return False
    if not _tenant_emails_enabled("overdue"):
        return False
    item = checkout.item
    if item is None:
        return False
    email = _resolve_recipient_email(checkout)
    if not email:
        return False
    try:
        return send_template_email(
            to=email,
            template_name="overdue",
            subject=f"Overdue: {item.label}",
            recipient_name=checkout.checked_out_to or "",
            tenant_name=tenant_name,
            item_label=item.label,
            item_custom_id=item.custom_id,
            item_type=item.type,
            item_address=item.address,
            quantity=checkout.quantity or 1,
            expected_return_date=checkout.expected_return_date,
            days_overdue=days_overdue,
            checkout_id=checkout.id,
        )
    except Exception:
        log.exception("notify_overdue failed for checkout=%r", checkout.id)
        return False
