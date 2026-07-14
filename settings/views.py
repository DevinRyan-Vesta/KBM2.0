"""Per-tenant settings pages.

Tenant-scoped (requires a subdomain). The main settings page is admin-only;
the API Keys page is open to every logged-in user (each user manages their
own keys, admins manage the whole account's).
"""
from datetime import timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from flask_login import login_required, current_user

from middleware.tenant_middleware import tenant_required
from utilities.database import get_tenant_settings, log_activity, utc_now
from utilities.master_database import master_db, ApiToken, MasterUser
from utilities.tenant_helpers import tenant_commit
from utilities.tenant_manager import tenant_manager


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


# ============================================================
# API Keys
# ============================================================

MAX_TOKENS_PER_USER = 25  # matches api/routes_tokens.py

_EXPIRY_CHOICES = {"never": None, "30": 30, "90": 90, "365": 365}


def _is_admin() -> bool:
    return (getattr(current_user, "role", "") or "").lower() in {"admin", "owner", "app_admin"}


def _visible_tokens_query():
    """Own tokens for regular users; the whole account's for admins."""
    if _is_admin():
        tenant = tenant_manager.get_current_tenant()
        return ApiToken.query.filter(ApiToken.account_id == tenant.id)
    return ApiToken.query.filter(ApiToken.user_id == current_user.id)


@settings_bp.get("/api-keys")
@login_required
@tenant_required
def api_keys():
    tokens = _visible_tokens_query().order_by(ApiToken.created_at.desc()).all()

    # Map user ids -> names so admins can see who owns each key.
    user_ids = {t.user_id for t in tokens}
    users = {}
    if user_ids:
        for u in MasterUser.query.filter(MasterUser.id.in_(user_ids)).all():
            users[u.id] = u.name

    # A token created on the previous request is shown exactly once (PRG:
    # the POST stashes it in the session, this GET pops it).
    new_token = session.pop("new_api_token", None)

    now = utc_now()
    return render_template(
        "settings_api_keys.html",
        tokens=tokens,
        token_users=users,
        new_token=new_token,
        now=now,
        is_admin=_is_admin(),
    )


@settings_bp.post("/api-keys")
@login_required
@tenant_required
def create_api_key():
    name = (request.form.get("name") or "").strip()[:120] or "API Token"
    expiry_choice = (request.form.get("expires") or "never").strip()
    expires_in_days = _EXPIRY_CHOICES.get(expiry_choice, None)

    active_count = ApiToken.query.filter_by(user_id=current_user.id, revoked_at=None).count()
    if active_count >= MAX_TOKENS_PER_USER:
        flash(f"You already have {active_count} active API keys. Revoke one before creating another.", "error")
        return redirect(url_for("settings.api_keys"))

    raw, prefix, token_hash = ApiToken.generate()
    token = ApiToken(
        account_id=current_user.account_id,
        user_id=current_user.id,
        name=name,
        token_prefix=prefix,
        token_hash=token_hash,
        expires_at=(utc_now() + timedelta(days=expires_in_days)) if expires_in_days else None,
    )
    master_db.session.add(token)
    master_db.session.commit()

    log_activity(
        "api_token_created",
        user=current_user,
        target_type="ApiToken",
        target_id=token.id,
        summary=f"Created API key \"{name}\" ({prefix}…)",
        meta={"expires_in_days": expires_in_days},
        commit=True,
    )

    session["new_api_token"] = raw
    flash("API key created. Copy it now — it won't be shown again.", "success")
    return redirect(url_for("settings.api_keys"))


@settings_bp.post("/api-keys/<int:token_id>/revoke")
@login_required
@tenant_required
def revoke_api_key(token_id: int):
    token = master_db.session.get(ApiToken, token_id)

    allowed = token is not None and (
        token.user_id == current_user.id
        or (_is_admin() and token.account_id == tenant_manager.get_current_tenant().id)
    )
    if not allowed:
        abort(404)

    if token.revoked_at is None:
        token.revoked_at = utc_now()
        master_db.session.commit()
        log_activity(
            "api_token_revoked",
            user=current_user,
            target_type="ApiToken",
            target_id=token.id,
            summary=f"Revoked API key \"{token.name}\" ({token.token_prefix}…)",
            commit=True,
        )
        flash(f"API key \"{token.name}\" revoked.", "success")
    else:
        flash("That API key was already revoked.", "info")

    return redirect(url_for("settings.api_keys"))
