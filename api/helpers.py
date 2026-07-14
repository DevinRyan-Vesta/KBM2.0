"""Shared plumbing for the REST API: auth, errors, pagination, parsing."""

import hmac
from datetime import datetime
from functools import wraps
from typing import Any, Dict, Optional, Tuple

from flask import g, jsonify, request

from utilities.master_database import master_db, ApiToken, MasterUser
from utilities.tenant_manager import tenant_manager
from utilities.database import utc_now

ADMIN_ROLES = ("admin", "owner", "app_admin")


# --- Errors -----------------------------------------------------------------

class ApiError(Exception):
    """Raise anywhere in an API handler to produce a structured JSON error."""

    def __init__(self, status: int, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details

    def to_response(self):
        body = {"error": {"code": self.code, "message": self.message}}
        if self.details:
            body["error"]["details"] = self.details
        return jsonify(body), self.status


def error(status: int, code: str, message: str, details: Optional[Dict[str, Any]] = None) -> ApiError:
    return ApiError(status, code, message, details)


def register_error_handlers(bp):
    @bp.errorhandler(ApiError)
    def _handle_api_error(exc: ApiError):
        return exc.to_response()


# --- Auth -------------------------------------------------------------------

def _extract_bearer_token() -> Optional[str]:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    # Fallback for clients that can't set headers (e.g. webhook test tools)
    return request.args.get("api_token") or None


def _resolve_token(raw: str) -> Tuple[ApiToken, MasterUser]:
    # Token format: kbm_<prefix>_<secret>
    parts = raw.split("_", 2)
    if len(parts) != 3 or parts[0] != ApiToken.TOKEN_ENV_PREFIX:
        raise error(401, "invalid_token", "Malformed API token.")

    token = ApiToken.query.filter_by(token_prefix=parts[1]).first()
    if token is None or not hmac.compare_digest(token.token_hash, ApiToken.hash_raw(raw)):
        raise error(401, "invalid_token", "Unknown or invalid API token.")
    if not token.is_valid():
        raise error(401, "token_revoked", "This API token has been revoked or has expired.")

    user = master_db.session.get(MasterUser, token.user_id)
    if user is None or not user.is_active:
        raise error(401, "user_inactive", "The user this token belongs to is inactive.")

    return token, user


def api_auth_required(f):
    """Authenticate the request with a Bearer token.

    Sets g.api_token and g.api_user. Does NOT require a tenant context —
    use api_tenant_required for tenant-scoped endpoints.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        raw = _extract_bearer_token()
        if not raw:
            raise error(401, "missing_token",
                        "Provide an API token via the 'Authorization: Bearer <token>' header.")
        token, user = _resolve_token(raw)

        g.api_token = token
        g.api_user = user

        token.last_used_at = utc_now()
        try:
            master_db.session.commit()
        except Exception:
            master_db.session.rollback()

        return f(*args, **kwargs)

    return wrapper


def api_tenant_required(f):
    """Bearer auth + require a tenant subdomain the token is allowed to use.

    A tenant token only works on its own account's subdomain. App-admin
    tokens (account_id NULL) work on any active tenant subdomain.
    """

    @wraps(f)
    @api_auth_required
    def wrapper(*args, **kwargs):
        tenant = tenant_manager.get_current_tenant()
        if tenant is None:
            raise error(404, "tenant_required",
                        "This endpoint must be called on a company subdomain "
                        "(e.g. https://yourcompany.example.com/api/v1/...).")

        user = g.api_user
        if (user.role or "").lower() != "app_admin" and user.account_id != tenant.id:
            raise error(403, "wrong_tenant", "This API token does not belong to this company.")

        return f(*args, **kwargs)

    return wrapper


def require_admin():
    """Abort with 403 unless the token's user is an admin/owner/app_admin."""
    role = (getattr(g.api_user, "role", "") or "").lower()
    if role not in ADMIN_ROLES:
        raise error(403, "admin_required", "This endpoint requires an admin role.")


# --- Request parsing ---------------------------------------------------------

def get_json_body() -> Dict[str, Any]:
    body = request.get_json(silent=True)
    if body is None:
        # Tolerate empty bodies on endpoints where every field is optional.
        if not request.data:
            return {}
        raise error(400, "invalid_json", "Request body must be valid JSON (Content-Type: application/json).")
    if not isinstance(body, dict):
        raise error(400, "invalid_json", "Request body must be a JSON object.")
    return body


def clean_str(value: Any, field: str, max_length: Optional[int] = None) -> Optional[str]:
    """Coerce a JSON value to a stripped string or None."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise error(400, "invalid_field", f"'{field}' must be a string.")
    value = value.strip()
    if max_length and len(value) > max_length:
        raise error(400, "invalid_field", f"'{field}' must be at most {max_length} characters.")
    return value or None


def clean_int(value: Any, field: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise error(400, "invalid_field", f"'{field}' must be an integer.")
    try:
        return int(value)
    except (TypeError, ValueError):
        raise error(400, "invalid_field", f"'{field}' must be an integer.")


def clean_bool(value: Any, field: str) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes"):
            return True
        if lowered in ("false", "0", "no"):
            return False
    raise error(400, "invalid_field", f"'{field}' must be a boolean.")


def parse_date(value: Any, field: str) -> Optional[datetime]:
    """Accept 'YYYY-MM-DD' or full ISO-8601 datetimes."""
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise error(400, "invalid_field", f"'{field}' must be a date string (YYYY-MM-DD).")
    value = value.strip()
    for fmt in ("%Y-%m-%d",):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.replace(tzinfo=None)
    except ValueError:
        raise error(400, "invalid_field", f"'{field}' is not a valid date. Use YYYY-MM-DD or ISO-8601.")


# --- Pagination ---------------------------------------------------------------

MAX_PER_PAGE = 100
DEFAULT_PER_PAGE = 25


def paginate(query):
    """Apply ?page=&per_page= to a query; return (rows, meta dict)."""
    page = request.args.get("page", 1, type=int) or 1
    per_page = request.args.get("per_page", DEFAULT_PER_PAGE, type=int) or DEFAULT_PER_PAGE
    page = max(page, 1)
    per_page = min(max(per_page, 1), MAX_PER_PAGE)

    total = query.count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    pages = (total + per_page - 1) // per_page if total else 0

    meta = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
    }
    return rows, meta


def list_response(key: str, rows, meta):
    return jsonify({key: [r.to_dict() for r in rows], "pagination": meta})
