"""REST API v1 for KBM.

All endpoints live under /api/v1 (registered in app_multitenant.py) and are
authenticated with Bearer tokens (see api/helpers.py). Tenant-scoped
endpoints must be called on the tenant's subdomain, exactly like the web UI.

Route modules attach themselves to api_bp on import.
"""

from flask import Blueprint

api_bp = Blueprint("api", __name__)

from api.helpers import register_error_handlers  # noqa: E402

register_error_handlers(api_bp)

# Import route modules for their side effect of registering routes.
from api import routes_meta  # noqa: E402,F401
from api import routes_tokens  # noqa: E402,F401
from api import routes_items  # noqa: E402,F401
from api import routes_checkouts  # noqa: E402,F401
from api import routes_properties  # noqa: E402,F401
from api import routes_contacts  # noqa: E402,F401
from api import routes_smartlocks  # noqa: E402,F401
from api import routes_audits  # noqa: E402,F401
from api import routes_admin  # noqa: E402,F401

__all__ = ["api_bp"]
