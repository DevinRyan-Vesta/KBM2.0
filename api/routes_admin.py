"""Admin-only endpoints: users, settings, activity logs, stats, accounts."""

from flask import g, jsonify, request

from api import api_bp
from api.helpers import (
    api_auth_required,
    api_tenant_required,
    clean_bool,
    clean_int,
    clean_str,
    error,
    get_json_body,
    paginate,
    require_admin,
)
from utilities.database import ActivityLog, Item, ItemCheckout, get_tenant_settings, log_activity, utc_now
from utilities.master_database import master_db, Account, MasterUser
from utilities.tenant_helpers import tenant_commit, tenant_query
from utilities.tenant_manager import tenant_manager

# Mirrors auth/views_multitenant.py — tenant-assignable roles.
ALLOWED_ROLES = ("admin", "owner", "user", "staff", "agent")


# --- Users --------------------------------------------------------------------

def _get_account_user_or_404(user_id: int) -> MasterUser:
    tenant = tenant_manager.get_current_tenant()
    user = MasterUser.query.filter_by(id=user_id, account_id=tenant.id).first()
    if user is None:
        raise error(404, "not_found", f"User {user_id} not found in this account.")
    return user


def _validate_pin(pin) -> str | None:
    if pin is None:
        return None
    pin = str(pin).strip()
    if not pin:
        return None
    if len(pin) < 4:
        raise error(400, "invalid_field", "'pin' must be at least 4 characters.")
    return pin


def _check_email_unique(email: str, account_id: int, exclude_user_id: int | None = None):
    clash = MasterUser.query.filter(
        master_db.func.lower(MasterUser.email) == email.lower(),
        MasterUser.account_id == account_id,
        MasterUser.id != (exclude_user_id or 0),
    ).first()
    if clash:
        raise error(409, "duplicate_email", "A user with this email already exists in this account.")


@api_bp.get("/users")
@api_tenant_required
def list_users():
    require_admin()
    tenant = tenant_manager.get_current_tenant()
    users = MasterUser.query.filter_by(account_id=tenant.id).order_by(MasterUser.name.asc()).all()
    return jsonify({"users": [u.to_dict() for u in users]})


@api_bp.post("/users")
@api_tenant_required
def create_user():
    require_admin()
    tenant = tenant_manager.get_current_tenant()
    body = get_json_body()

    name = clean_str(body.get("name"), "name", 200)
    email = clean_str(body.get("email"), "email", 255)
    role = (clean_str(body.get("role"), "role", 20) or "user").lower()
    pin = _validate_pin(body.get("pin"))

    if not name:
        raise error(400, "invalid_field", "'name' is required.")
    if not email:
        raise error(400, "invalid_field", "'email' is required.")
    if not pin:
        raise error(400, "invalid_field", "'pin' is required.")
    if role not in ALLOWED_ROLES:
        raise error(400, "invalid_field", f"'role' must be one of: {', '.join(ALLOWED_ROLES)}.")
    _check_email_unique(email, tenant.id)

    max_users = tenant.max_users or 0
    if max_users:
        current = MasterUser.query.filter_by(account_id=tenant.id).count()
        if current >= max_users:
            raise error(409, "user_limit", f"This account has reached its user limit ({max_users}).")

    user = MasterUser(account_id=tenant.id, name=name, email=email, role=role, is_active=True)
    user.set_pin(pin)
    master_db.session.add(user)
    master_db.session.commit()
    return jsonify(user.to_dict()), 201


@api_bp.get("/users/<int:user_id>")
@api_tenant_required
def get_user(user_id: int):
    require_admin()
    return jsonify(_get_account_user_or_404(user_id).to_dict())


@api_bp.patch("/users/<int:user_id>")
@api_tenant_required
def update_user(user_id: int):
    require_admin()
    tenant = tenant_manager.get_current_tenant()
    user = _get_account_user_or_404(user_id)
    body = get_json_body()

    if "name" in body:
        name = clean_str(body.get("name"), "name", 200)
        if not name:
            raise error(400, "invalid_field", "'name' cannot be blank.")
        user.name = name
    if "email" in body:
        email = clean_str(body.get("email"), "email", 255)
        if not email:
            raise error(400, "invalid_field", "'email' cannot be blank.")
        _check_email_unique(email, tenant.id, exclude_user_id=user.id)
        user.email = email
    if "role" in body:
        role = (clean_str(body.get("role"), "role", 20) or "").lower()
        if role not in ALLOWED_ROLES:
            raise error(400, "invalid_field", f"'role' must be one of: {', '.join(ALLOWED_ROLES)}.")
        user.role = role
    if "is_active" in body:
        is_active = clean_bool(body.get("is_active"), "is_active")
        if user.id == g.api_user.id and is_active is False:
            raise error(400, "invalid_field", "You cannot deactivate your own account.")
        user.is_active = bool(is_active)
    if "pin" in body:
        pin = _validate_pin(body.get("pin"))
        if pin:
            user.set_pin(pin)

    master_db.session.commit()
    return jsonify(user.to_dict())


@api_bp.delete("/users/<int:user_id>")
@api_tenant_required
def delete_user(user_id: int):
    require_admin()
    if user_id == g.api_user.id:
        raise error(400, "invalid_field", "You cannot remove your own account.")
    user = _get_account_user_or_404(user_id)
    master_db.session.delete(user)
    master_db.session.commit()
    return jsonify({"deleted": True, "id": user_id})


# --- Settings -------------------------------------------------------------------

SETTINGS_BOOL_FIELDS = ("email_notifications_enabled", "notify_on_checkout",
                        "notify_on_checkin", "notify_on_overdue")
SETTINGS_INT_FIELDS = ("overdue_grace_days", "low_keys_threshold", "default_checkout_days")
SETTINGS_TEXT_FIELDS = ("receipt_header", "receipt_footer")


@api_bp.get("/settings")
@api_tenant_required
def get_settings():
    require_admin()
    return jsonify(get_tenant_settings().to_dict())


@api_bp.patch("/settings")
@api_tenant_required
def update_settings():
    require_admin()
    settings = get_tenant_settings()
    body = get_json_body()

    known = set(SETTINGS_BOOL_FIELDS) | set(SETTINGS_INT_FIELDS) | set(SETTINGS_TEXT_FIELDS)
    unknown = set(body.keys()) - known
    if unknown:
        raise error(400, "unknown_fields", f"Unknown setting(s): {', '.join(sorted(unknown))}.")

    for field in SETTINGS_BOOL_FIELDS:
        if field in body:
            value = clean_bool(body.get(field), field)
            if value is None:
                raise error(400, "invalid_field", f"'{field}' cannot be null.")
            setattr(settings, field, value)
    for field in SETTINGS_INT_FIELDS:
        if field in body:
            value = clean_int(body.get(field), field)
            if value is None or value < 0:
                raise error(400, "invalid_field", f"'{field}' must be a non-negative integer.")
            setattr(settings, field, value)
    for field in SETTINGS_TEXT_FIELDS:
        if field in body:
            setattr(settings, field, clean_str(body.get(field), field))

    log_activity("settings_updated", user=g.api_user, target=settings,
                 summary="Updated tenant settings via API",
                 meta={"fields": sorted(set(body.keys()))}, commit=False)
    tenant_commit()
    return jsonify(settings.to_dict())


# --- Activity logs ----------------------------------------------------------------

@api_bp.get("/activity-logs")
@api_tenant_required
def list_activity_logs():
    require_admin()
    query = tenant_query(ActivityLog)

    action = request.args.get("action")
    if action:
        query = query.filter(ActivityLog.action == action)

    user_id = request.args.get("user_id", type=int)
    if user_id:
        query = query.filter(ActivityLog.user_id == user_id)

    target_type = request.args.get("target_type")
    if target_type:
        query = query.filter(ActivityLog.target_type == target_type)

    query = query.order_by(ActivityLog.created_at.desc())
    rows, meta = paginate(query)
    return jsonify({"activity_logs": [r.to_dict() for r in rows], "pagination": meta})


# --- Stats -------------------------------------------------------------------------

@api_bp.get("/stats")
@api_tenant_required
def stats():
    """Dashboard-style summary: item counts, active checkouts, overdue."""
    by_type_status = {}
    for item_type, status, count in (
        tenant_query(Item)
        .with_entities(Item.type, Item.status, master_db.func.count(Item.id))
        .group_by(Item.type, Item.status)
        .all()
    ):
        by_type_status.setdefault(item_type, {})[status] = count

    active_checkouts = tenant_query(ItemCheckout).filter_by(is_active=True).count()
    overdue = tenant_query(ItemCheckout).filter(
        ItemCheckout.is_active.is_(True),
        ItemCheckout.expected_return_date.isnot(None),
        ItemCheckout.expected_return_date < utc_now(),
    ).count()

    return jsonify({
        "items": by_type_status,
        "active_checkouts": active_checkouts,
        "overdue_checkouts": overdue,
    })


# --- Accounts (app admin, root domain) ------------------------------------------------

@api_bp.get("/accounts")
@api_auth_required
def list_accounts():
    if (g.api_user.role or "").lower() != "app_admin":
        raise error(403, "admin_required", "This endpoint requires an app admin token.")
    accounts = Account.query.order_by(Account.company_name.asc()).all()
    return jsonify({"accounts": [a.to_dict() for a in accounts]})
