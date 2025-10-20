"""
Tenant database connection manager.
Handles dynamic connection to tenant-specific databases.
"""

from pathlib import Path
from flask import g, current_app
from sqlalchemy import create_engine, event
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import StaticPool
import os


class TenantManager:
    """
    Manages tenant database connections and context.
    Each tenant has a separate SQLite database file.
    """

    def __init__(self, app=None):
        self.app = app
        self._engines = {}  # Cache of tenant database engines
        self._sessions = {}  # Cache of tenant sessions

        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize the tenant manager with Flask app."""
        self.app = app

        # Set up teardown to close tenant sessions
        @app.teardown_appcontext
        def shutdown_session(exception=None):
            self.close_tenant_session()

    def get_tenant_database_path(self, account) -> Path:
        """
        Get the file path for a tenant's database.

        Args:
            account: Account object or subdomain string

        Returns:
            Path object for the database file
        """
        if isinstance(account, str):
            subdomain = account
        else:
            subdomain = account.subdomain

        base_dir = Path(self.app.config.get('TENANT_DATA_DIR', 'tenant_dbs'))
        base_dir.mkdir(parents=True, exist_ok=True)

        db_path = (base_dir / f"{subdomain}.db").resolve()
        return db_path

    def create_tenant_database(self, account) -> Path:
        """
        Create a new database file for a tenant and run migrations.

        Args:
            account: Account model instance

        Returns:
            Path to the created database file
        """
        db_path = self.get_tenant_database_path(account)

        # Ensure the directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create the database URI
        db_uri = f"sqlite:///{db_path.as_posix()}"

        # Create engine and session
        engine = create_engine(
            db_uri,
            connect_args={'check_same_thread': False},
            poolclass=StaticPool,
            echo=self.app.config.get('SQLALCHEMY_ECHO', False)
        )

        # Import models to register them
        from utilities.database import db

        # Create all tables
        with self.app.app_context():
            db.metadata.create_all(bind=engine)

        print(f"Created tenant database at: {db_path}")
        return db_path

    def get_tenant_engine(self, account):
        """
        Get or create a SQLAlchemy engine for a tenant.

        Args:
            account: Account model instance or subdomain string

        Returns:
            SQLAlchemy engine for the tenant database
        """
        if isinstance(account, str):
            subdomain = account
        else:
            subdomain = account.subdomain

        # Return cached engine if available
        if subdomain in self._engines:
            return self._engines[subdomain]

        # Get database path
        db_path = self.get_tenant_database_path(account)

        if not db_path.exists():
            raise FileNotFoundError(f"Tenant database not found: {db_path}")

        # Create engine
        db_uri = f"sqlite:///{db_path.as_posix()}"
        engine = create_engine(
            db_uri,
            connect_args={'check_same_thread': False},
            poolclass=StaticPool,
            echo=self.app.config.get('SQLALCHEMY_ECHO', False)
        )

        # Enable foreign keys for SQLite
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        # Cache the engine
        self._engines[subdomain] = engine

        return engine

    def get_tenant_session(self, account):
        """
        Get or create a database session for a tenant.

        Args:
            account: Account model instance or subdomain string

        Returns:
            SQLAlchemy session for the tenant database
        """
        if isinstance(account, str):
            subdomain = account
        else:
            subdomain = account.subdomain

        # Return cached session if available
        if subdomain in self._sessions:
            return self._sessions[subdomain]

        # Get engine
        engine = self.get_tenant_engine(account)

        # Create session
        Session = scoped_session(sessionmaker(bind=engine))
        session = Session()

        # Cache the session
        self._sessions[subdomain] = session

        return session

    def set_tenant_context(self, account):
        """
        Set the current tenant context in Flask's g object.
        This should be called by middleware for each request.

        Args:
            account: Account model instance
        """
        g.tenant = account
        g.tenant_db_session = self.get_tenant_session(account)

    def get_current_tenant(self):
        """
        Get the current tenant from Flask's g object.

        Returns:
            Account model instance or None
        """
        return getattr(g, 'tenant', None)

    def get_current_session(self):
        """
        Get the current tenant's database session.

        Returns:
            SQLAlchemy session or None
        """
        return getattr(g, 'tenant_db_session', None)

    def close_tenant_session(self):
        """Close the current tenant session if it exists."""
        session = getattr(g, 'tenant_db_session', None)
        if session:
            session.close()
            g.pop('tenant_db_session', None)

    def query_tenant_db(self, model_class):
        """
        Helper to query the current tenant's database.

        Args:
            model_class: SQLAlchemy model class to query

        Returns:
            Query object for the model

        Example:
            items = tenant_manager.query_tenant_db(Item).all()
        """
        session = self.get_current_session()
        if not session:
            raise RuntimeError("No tenant context set. Make sure you're in a tenant request.")

        return session.query(model_class)

    def delete_tenant_database(self, account):
        """
        Delete a tenant's database file (use with caution!).

        Args:
            account: Account model instance
        """
        db_path = self.get_tenant_database_path(account)

        # Close any open connections
        subdomain = account.subdomain if hasattr(account, 'subdomain') else account

        if subdomain in self._sessions:
            self._sessions[subdomain].close()
            del self._sessions[subdomain]

        if subdomain in self._engines:
            self._engines[subdomain].dispose()
            del self._engines[subdomain]

        # Delete the file
        if db_path.exists():
            db_path.unlink()
            print(f"Deleted tenant database: {db_path}")


# Global tenant manager instance
tenant_manager = TenantManager()
