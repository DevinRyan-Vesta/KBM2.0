"""
Flask extensions that need to be importable from anywhere.

Lives outside of `app_multitenant` so blueprints can import from this module
without creating circular imports back to the app factory.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


# Global rate limiter. The app factory in `app_multitenant` always calls
# `limiter.init_app(app)`; set RATELIMIT_ENABLED=false in the environment to
# disable enforcement (e.g. for local development or tests).
#
# No `default_limits` on purpose: only sensitive routes opt in with an
# explicit `@limiter.limit(...)` (login, signup). A global default would
# throttle normal page browsing for busy office users.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    strategy="fixed-window",
)
