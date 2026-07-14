"""API token lifecycle: create (email+PIN login), list, revoke.

Token creation is the only API endpoint that authenticates with credentials
instead of a Bearer token, so it is rate-limited like the web login.
"""

from datetime import timedelta

from flask import g, jsonify

from api import api_bp
from api.helpers import (
    api_auth_required,
    clean_int,
    clean_str,
    error,
    get_json_body,
)
from utilities.database import utc_now
from utilities.extensions import limiter
from utilities.master_database import master_db, ApiToken, MasterUser
from utilities.tenant_manager import tenant_manager

MAX_TOKENS_PER_USER = 25


@api_bp.post("/auth/tokens")
@limiter.limit("10 per minute; 30 per hour")
def create_token():
    """Exchange email + PIN for a long-lived API token.

    Must be called on the company subdomain for tenant users. App admins
    call it on the root domain and get a cross-tenant token.
    """
    body = get_json_body()
    email = clean_str(body.get("email"), "email", 255)
    pin = body.get("pin")
    pin = str(pin).strip() if pin is not None else ""
    name = clean_str(body.get("name"), "name", 120) or "API Token"
    expires_in_days = clean_int(body.get("expires_in_days"), "expires_in_days")

    if not email or not pin:
        raise error(400, "missing_credentials", "Both 'email' and 'pin' are required.")
    if expires_in_days is not None and expires_in_days < 1:
        raise error(400, "invalid_field", "'expires_in_days' must be a positive integer.")

    tenant = tenant_manager.get_current_tenant()
    if tenant is not None:
        user = MasterUser.query.filter(
            master_db.func.lower(MasterUser.email) == email.lower(),
            MasterUser.account_id == tenant.id,
            MasterUser.is_active.is_(True),
        ).first()
    else:
        # Root domain: only app admins may mint tokens here.
        user = MasterUser.query.filter(
            master_db.func.lower(MasterUser.email) == email.lower(),
            MasterUser.role == "app_admin",
            MasterUser.is_active.is_(True),
        ).first()

    if user is None or not user.check_pin(pin):
        raise error(401, "invalid_credentials", "Email or PIN is incorrect.")

    active_count = ApiToken.query.filter_by(user_id=user.id, revoked_at=None).count()
    if active_count >= MAX_TOKENS_PER_USER:
        raise error(409, "token_limit",
                    f"You already have {active_count} active tokens. Revoke one before creating another.")

    raw, prefix, token_hash = ApiToken.generate()
    token = ApiToken(
        account_id=user.account_id,
        user_id=user.id,
        name=name,
        token_prefix=prefix,
        token_hash=token_hash,
        expires_at=(utc_now() + timedelta(days=expires_in_days)) if expires_in_days else None,
    )
    master_db.session.add(token)
    master_db.session.commit()

    payload = token.to_dict()
    payload["token"] = raw  # shown exactly once
    return jsonify(payload), 201


@api_bp.get("/auth/tokens")
@api_auth_required
def list_tokens():
    """List your own tokens. Admins see every token in the account."""
    user = g.api_user
    role = (user.role or "").lower()

    query = ApiToken.query
    if role == "app_admin":
        query = query.filter(ApiToken.account_id.is_(None))
    elif role in ("admin", "owner"):
        query = query.filter(ApiToken.account_id == user.account_id)
    else:
        query = query.filter(ApiToken.user_id == user.id)

    tokens = query.order_by(ApiToken.created_at.desc()).all()
    return jsonify({"tokens": [t.to_dict() for t in tokens]})


@api_bp.delete("/auth/tokens/<int:token_id>")
@api_auth_required
def revoke_token(token_id: int):
    """Revoke a token. Users can revoke their own; admins any in the account."""
    user = g.api_user
    role = (user.role or "").lower()

    token = master_db.session.get(ApiToken, token_id)
    if token is None:
        raise error(404, "not_found", "Token not found.")

    allowed = token.user_id == user.id
    if role == "app_admin":
        allowed = True
    elif role in ("admin", "owner") and token.account_id == user.account_id:
        allowed = True
    if not allowed:
        raise error(403, "forbidden", "You cannot revoke this token.")

    if token.revoked_at is None:
        token.revoked_at = utc_now()
        master_db.session.commit()

    return jsonify({"revoked": True, "id": token.id})
