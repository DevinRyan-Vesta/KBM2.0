"""
Tenant middleware for subdomain-based routing.
Extracts subdomain from request and sets tenant context.
"""

from flask import request, g, abort, redirect, url_for
from utilities.master_database import master_db, Account
from utilities.tenant_manager import tenant_manager
from functools import wraps


class TenantMiddleware:
    """
    Middleware to handle multi-tenant subdomain routing.

    Request flow:
    1. Extract subdomain from request
    2. Look up account in master database
    3. Set tenant context for the request
    4. Route to appropriate handler
    """

    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize middleware with Flask app."""
        self.app = app

        # Register before_request handler
        app.before_request(self.load_tenant)

    def extract_subdomain(self, request) -> str | None:
        """
        Extract subdomain from request.

        Examples:
            vesta.example.com -> "vesta"
            vesta.localhost:5000 -> "vesta"
            example.com -> None (root domain)
            localhost:5000 -> None (root domain)

        Returns:
            Subdomain string or None if root domain
        """
        host = request.host.lower()

        # Remove port if present
        if ':' in host:
            host = host.split(':')[0]

        # Get configured server name (e.g., "example.com" or "localhost")
        server_name = self.app.config.get('SERVER_NAME') or 'localhost'
        if server_name and ':' in server_name:
            server_name = server_name.split(':')[0]

        # Handle localhost specially
        if 'localhost' in host:
            if '.' in host:
                # Format: subdomain.localhost
                parts = host.split('.')
                if len(parts) > 1 and parts[0] != 'localhost':
                    return parts[0]
            return None

        # Handle regular domains
        if host.endswith(f'.{server_name}'):
            # Extract subdomain
            subdomain = host.replace(f'.{server_name}', '')
            if subdomain and subdomain != server_name:
                return subdomain

        # Check if this is the root domain
        if host == server_name:
            return None

        return None

    def load_tenant(self):
        """
        Load tenant context before each request.
        This runs before every request to set up the tenant.
        """
        # Extract subdomain
        subdomain = self.extract_subdomain(request)

        # Mark whether this is a root domain request
        g.is_root_domain = subdomain is None

        if subdomain:
            # Look up account in master database
            account = Account.query.filter_by(subdomain=subdomain).first()

            if not account:
                # Subdomain not found
                abort(404, description=f"Account '{subdomain}' not found")

            if account.status != 'active':
                # Account is suspended or deleted
                abort(403, description=f"Account '{subdomain}' is not active")

            # Set tenant context
            try:
                tenant_manager.set_tenant_context(account)
                g.subdomain = subdomain
            except FileNotFoundError:
                # Database file missing
                abort(500, description=f"Database for account '{subdomain}' is not available")
        else:
            # Root domain - no tenant context
            g.tenant = None
            g.tenant_db_session = None
            g.subdomain = None


def tenant_required(f):
    """
    Decorator to require a tenant context.
    Use this on routes that should only be accessible on a subdomain.

    Example:
        @app.route('/items')
        @tenant_required
        def list_items():
            # This will only work on subdomain.example.com
            items = tenant_manager.query_tenant_db(Item).all()
            return render_template('items.html', items=items)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not tenant_manager.get_current_tenant():
            return abort(404, description="This page is only accessible from a company subdomain")
        return f(*args, **kwargs)
    return decorated_function


def root_domain_only(f):
    """
    Decorator to require root domain (no subdomain).
    Use this on routes that should only be accessible on the root domain.

    Example:
        @app.route('/signup')
        @root_domain_only
        def signup():
            # This will only work on example.com (not subdomain.example.com)
            return render_template('signup.html')
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.get('is_root_domain', False):
            return abort(404, description="This page is only accessible from the root domain")
        return f(*args, **kwargs)
    return decorated_function


def app_admin_required(f):
    """
    Decorator to require app admin authentication.
    Use this for app-level admin routes.

    Example:
        @app.route('/admin/accounts')
        @app_admin_required
        def manage_accounts():
            # Only app admins can access this
            accounts = Account.query.all()
            return render_template('admin/accounts.html', accounts=accounts)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask_login import current_user

        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))

        if current_user.role != 'app_admin':
            abort(403, description="This page requires app admin privileges")

        return f(*args, **kwargs)
    return decorated_function


# Global middleware instance
tenant_middleware = TenantMiddleware()
