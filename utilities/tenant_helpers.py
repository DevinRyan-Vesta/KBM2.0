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


def get_page_args(default_per_page=50, max_per_page=200):
    """
    Read `page` and `per_page` from the current request's query string.

    Values are parsed defensively: anything non-numeric falls back to the
    defaults, page is clamped to >= 1 and per_page to 1..max_per_page.

    Returns:
        (page, per_page) tuple of ints
    """
    from flask import request

    def _int_arg(name, default):
        raw = request.args.get(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    page = max(1, _int_arg("page", 1))
    per_page = _int_arg("per_page", default_per_page)
    per_page = max(1, min(per_page, max_per_page))
    return page, per_page


def paginate_query(query, page, per_page, max_per_page=200):
    """
    Paginate a plain SQLAlchemy query (tenant sessions are raw SQLAlchemy,
    so Flask-SQLAlchemy's .paginate() is not available).

    Args:
        query: SQLAlchemy Query with all filters/ordering already applied
        page: 1-based page number (clamped to valid range)
        per_page: items per page (clamped to 1..max_per_page)
        max_per_page: hard cap on per_page

    Returns:
        dict with keys: items, page, per_page, total, pages, has_prev, has_next
    """
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(per_page)
    except (TypeError, ValueError):
        per_page = 50
    page = max(1, page)
    per_page = max(1, min(per_page, max_per_page))

    total = query.count()
    pages = (total + per_page - 1) // per_page if total else 0
    if pages and page > pages:
        page = pages

    items = query.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "has_prev": page > 1,
        "has_next": page < pages,
    }


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
