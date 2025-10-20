from flask import Blueprint, render_template, url_for, redirect, g
from flask_login import login_required, current_user
from utilities.database import db, User, Item, utc_now
from utilities.tenant_manager import tenant_manager
from middleware.tenant_middleware import tenant_required
from datetime import timedelta
from sqlalchemy import func, or_


main_bp = Blueprint(
    "main",
    __name__,
    template_folder="../templates",
    static_folder="../static"
)


def get_tenant_session():
    """Get the current tenant database session."""
    session = tenant_manager.get_current_session()
    if not session:
        from flask import abort
        abort(500, description="Tenant database session not available")
    return session


@main_bp.route("/", methods=["GET"])
@login_required
@tenant_required
def home():
    # Calculate statistics for the dashboard
    session = get_tenant_session()

    # Lockbox stats
    lockbox_total = session.query(Item).filter_by(type="Lockbox").count()
    lockbox_available = session.query(Item).filter_by(type="Lockbox", status="available").count()
    lockbox_checked_out = session.query(Item).filter_by(type="Lockbox", status="checked_out").count()
    lockbox_assigned = session.query(Item).filter_by(type="Lockbox", status="assigned").count()

    # Key stats
    key_total = session.query(Item).filter_by(type="Key").count()
    key_available_count = session.query(func.sum(Item.total_copies - Item.copies_checked_out)).filter(
        Item.type == "Key"
    ).scalar() or 0
    key_checked_out_count = session.query(func.sum(Item.copies_checked_out)).filter(
        Item.type == "Key"
    ).scalar() or 0

    # Keys with less than 6 copies
    keys_low_copies = session.query(Item).filter(
        Item.type == "Key",
        Item.total_copies < 6
    ).order_by(Item.total_copies.asc()).limit(10).all()

    # Sign stats
    sign_total = session.query(Item).filter_by(type="Sign").count()
    sign_available = session.query(Item).filter_by(type="Sign", status="available").count()
    sign_checked_out = session.query(Item).filter_by(type="Sign", status="checked_out").count()

    # Items with expected return dates (upcoming and overdue)
    today = utc_now()
    next_week = today + timedelta(days=7)

    # Upcoming returns (next 7 days) - exclude tenant and property assignments
    upcoming_returns = session.query(Item).filter(
        Item.expected_return_date.isnot(None),
        Item.expected_return_date >= today,
        Item.expected_return_date <= next_week,
        or_(
            Item.assignment_type == "contractor",
            Item.assignment_type.is_(None)
        )
    ).order_by(Item.expected_return_date.asc()).all()

    # Overdue items - exclude tenant and property assignments
    overdue_items = session.query(Item).filter(
        Item.expected_return_date.isnot(None),
        Item.expected_return_date < today,
        or_(
            Item.assignment_type == "contractor",
            Item.assignment_type.is_(None)
        )
    ).order_by(Item.expected_return_date.asc()).all()

    # Items checked out for a long time (>30 days) - exclude tenant and property assignments
    thirty_days_ago = today - timedelta(days=30)
    long_checkout_items = session.query(Item).filter(
        Item.status.in_(["checked_out", "assigned"]),
        Item.last_action_at < thirty_days_ago,
        or_(
            Item.assignment_type == "contractor",
            Item.assignment_type.is_(None)
        )
    ).order_by(Item.last_action_at.asc()).limit(10).all()

    return render_template(
        "home.html",
        # Lockbox stats
        lockbox_total=lockbox_total,
        lockbox_available=lockbox_available,
        lockbox_checked_out=lockbox_checked_out,
        lockbox_assigned=lockbox_assigned,
        # Key stats
        key_total=key_total,
        key_available_count=key_available_count,
        key_checked_out_count=key_checked_out_count,
        keys_low_copies=keys_low_copies,
        # Sign stats
        sign_total=sign_total,
        sign_available=sign_available,
        sign_checked_out=sign_checked_out,
        # Return tracking
        upcoming_returns=upcoming_returns,
        overdue_items=overdue_items,
        long_checkout_items=long_checkout_items,
    )


@main_bp.route("/reports", methods=["GET"])
@login_required
@tenant_required
def reports():
    # Calculate comprehensive statistics for reports page
    session = get_tenant_session()
    today = utc_now()
    thirty_days_ago = today - timedelta(days=30)
    next_week = today + timedelta(days=7)
    next_month = today + timedelta(days=30)

    # All overdue items
    all_overdue = session.query(Item).filter(
        Item.expected_return_date.isnot(None),
        Item.expected_return_date < today,
        or_(
            Item.assignment_type == "contractor",
            Item.assignment_type.is_(None)
        )
    ).order_by(Item.expected_return_date.asc()).all()

    # All upcoming returns (next 30 days)
    all_upcoming = session.query(Item).filter(
        Item.expected_return_date.isnot(None),
        Item.expected_return_date >= today,
        Item.expected_return_date <= next_month,
        or_(
            Item.assignment_type == "contractor",
            Item.assignment_type.is_(None)
        )
    ).order_by(Item.expected_return_date.asc()).all()

    # Long-term checkouts (>30 days)
    long_term = session.query(Item).filter(
        Item.status.in_(["checked_out", "assigned"]),
        Item.last_action_at < thirty_days_ago,
        or_(
            Item.assignment_type == "contractor",
            Item.assignment_type.is_(None)
        )
    ).order_by(Item.last_action_at.asc()).all()

    # All keys with less than 6 copies
    all_keys_low = session.query(Item).filter(
        Item.type == "Key",
        Item.total_copies < 6
    ).order_by(Item.total_copies.asc()).all()

    # Keys with 0 available copies
    keys_no_available = session.query(Item).filter(
        Item.type == "Key",
        Item.total_copies == Item.copies_checked_out
    ).all()

    # All assigned items by type
    tenant_assignments = session.query(Item).filter_by(assignment_type="tenant").all()
    contractor_assignments = session.query(Item).filter_by(assignment_type="contractor").all()
    property_assignments = session.query(Item).filter_by(assignment_type="property").all()

    # Items by status
    all_checked_out = session.query(Item).filter_by(status="checked_out").order_by(Item.last_action_at.desc()).all()
    all_assigned = session.query(Item).filter_by(status="assigned").order_by(Item.last_action_at.desc()).all()

    return render_template(
        "reports.html",
        all_overdue=all_overdue,
        all_upcoming=all_upcoming,
        long_term=long_term,
        all_keys_low=all_keys_low,
        keys_no_available=keys_no_available,
        tenant_assignments=tenant_assignments,
        contractor_assignments=contractor_assignments,
        property_assignments=property_assignments,
        all_checked_out=all_checked_out,
        all_assigned=all_assigned,
    )
