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


@settings_bp.post("/")
@login_required
@tenant_required
def save_settings():
    _require_tenant_admin()
    settings = get_tenant_settings()

    # Checkbox: present in form when checked, absent when unchecked.
    settings.email_notifications_enabled = bool(request.form.get("email_notifications_enabled"))

    # Optional free-text fields
    header = (request.form.get("receipt_header") or "").strip()
    footer = (request.form.get("receipt_footer") or "").strip()
    settings.receipt_header = header or None
    settings.receipt_footer = footer or None

    tenant_commit()
    flash("Settings saved.", "success")
    return redirect(url_for("settings.settings_page"))
