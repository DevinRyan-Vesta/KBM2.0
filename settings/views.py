"""Per-tenant settings page.

Tenant-scoped (requires a subdomain) and admin-only. Stores config in the
tenant DB via TenantSettings.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from middleware.tenant_middleware import tenant_required
from utilities.database import get_tenant_settings
from utilities.tenant_helpers import tenant_commit


settings_bp = Blueprint(
    "settings",
    __name__,
    template_folder="../templates",
)


def _require_tenant_admin():
    """Only admins (and owners) can edit tenant settings."""
    role = (getattr(current_user, "role", "") or "").lower()
    if role not in {"admin", "owner"}:
        abort(403)


@settings_bp.get("/")
@login_required
@tenant_required
def settings_page():
    _require_tenant_admin()
    settings = get_tenant_settings()
    return render_template("settings.html", settings=settings)


def _form_int(name: str, default: int, *, minimum: int = 0, maximum: int | None = None) -> int:
    """Parse a form value as int, clamped to [minimum, maximum]. Falls back
    to `default` on missing / invalid input so a typo can't break the page."""
    raw = (request.form.get(name) or "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    if value < minimum:
        value = minimum
    if maximum is not None and value > maximum:
        value = maximum
    return value


@settings_bp.post("/")
@login_required
@tenant_required
def save_settings():
    _require_tenant_admin()
    settings = get_tenant_settings()

    # Email — master switch + per-event flags. Unchecked checkboxes don't
    # appear in form data, so we read each as truthy/false from presence.
    settings.email_notifications_enabled = bool(request.form.get("email_notifications_enabled"))
    settings.notify_on_checkout = bool(request.form.get("notify_on_checkout"))
    settings.notify_on_checkin = bool(request.form.get("notify_on_checkin"))
    settings.notify_on_overdue = bool(request.form.get("notify_on_overdue"))

    # Numeric thresholds (clamped to sane ranges so a typo can't crash queries).
    settings.overdue_grace_days = _form_int("overdue_grace_days", default=0, minimum=0, maximum=365)
    settings.low_keys_threshold = _form_int("low_keys_threshold", default=4, minimum=0, maximum=999)
    settings.default_checkout_days = _form_int("default_checkout_days", default=7, minimum=0, maximum=365)

    # Optional free-text fields
    header = (request.form.get("receipt_header") or "").strip()
    footer = (request.form.get("receipt_footer") or "").strip()
    settings.receipt_header = header or None
    settings.receipt_footer = footer or None

    tenant_commit()
    flash("Settings saved.", "success")
    return redirect(url_for("settings.settings_page"))
