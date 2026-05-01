"""
Flask extensions that need to be importable from anywhere.

Lives outside of `app_multitenant` so blueprints can import from this module
without creating circular imports back to the app factory.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


# Global rate limiter. The app factory in `app_multitenant` calls
# `limiter.init_app(app)` only when RATELIMIT_ENABLED is true; until then
# every `@limiter.limit(...)` decorator becomes a no-op, which is the
# behavior we want for dev / unconfigured environments.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window",
)
