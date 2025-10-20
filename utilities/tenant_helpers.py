"""
Helper functions for tenant-aware database queries.
This makes it easy to migrate existing code to multi-tenant.
"""

from utilities.tenant_manager import tenant_manager
from flask import abort


def get_tenant_session():
    """
    Get the current tenant database session.

    Returns:
        SQLAlchemy session for the current tenant

    Raises:
        500 error if no tenant session is available
    """
    session = tenant_manager.get_current_session()
    if not session:
        abort(500, description="Tenant database session not available")
    return session


def tenant_query(model_class):
    """
    Create a query for the current tenant's database.

    Args:
        model_class: The SQLAlchemy model class to query

    Returns:
        Query object

    Example:
        items = tenant_query(Item).filter_by(type="Key").all()
    """
    session = get_tenant_session()
    return session.query(model_class)


def tenant_add(obj):
    """
    Add an object to the current tenant's database session.

    Args:
        obj: The model instance to add
    """
    session = get_tenant_session()
    session.add(obj)


def tenant_delete(obj):
    """
    Delete an object from the current tenant's database.

    Args:
        obj: The model instance to delete
    """
    session = get_tenant_session()
    session.delete(obj)


def tenant_commit():
    """
    Commit changes to the current tenant's database.
    """
    session = get_tenant_session()
    session.commit()


def tenant_rollback():
    """
    Rollback changes to the current tenant's database.
    """
    session = get_tenant_session()
    session.rollback()


def tenant_flush():
    """
    Flush changes to the current tenant's database.
    """
    session = get_tenant_session()
    session.flush()
