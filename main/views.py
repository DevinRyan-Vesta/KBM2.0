from flask import Blueprint, render_template, url_for, redirect, g, request
from flask_login import login_required, current_user
from utilities.database import db, User, Item, ItemCheckout, utc_now
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
def home():
    # Root domain has no tenant: show the public landing page (signup /
    # login). The tenant dashboard below only exists on subdomains. This
    # branch must run before any auth check, so visitors aren't bounced to
    # a login form that can't help them.
    if g.get("is_root_domain", False):
        return render_template("landing.html")

    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.url))

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

    # Keys below the tenant's configured low-keys threshold (Settings page).
    from utilities.database import get_tenant_settings
    low_keys_threshold = get_tenant_settings().low_keys_threshold
    keys_low_copies = session.query(Item).filter(
        Item.type == "Key",
        Item.total_copies < low_keys_threshold
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

    # --- Dashboard analytics -------------------------------------------
    # Checkouts per week: last 8 ISO weeks (Mon-Sun), including the current
    # week. Buckets are computed in Python so we don't need any
    # dialect-specific SQL date math (tenant DBs are SQLite).
    current_week_start = (today - timedelta(days=today.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    week_starts = [current_week_start - timedelta(weeks=offset) for offset in range(7, -1, -1)]
    week_counts = {week_start: 0 for week_start in week_starts}
    recent_checkout_times = session.query(ItemCheckout.checked_out_at).filter(
        ItemCheckout.checked_out_at >= week_starts[0]
    ).all()
    for (checked_out_at,) in recent_checkout_times:
        if not checked_out_at:
            continue
        bucket = (checked_out_at - timedelta(days=checked_out_at.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        if bucket in week_counts:
            week_counts[bucket] += 1

    # Bar heights as a percent of the busiest week; guard divide-by-zero
    # when there were no checkouts at all. Tiny-but-nonzero weeks get a
    # visible floor so a 1-count bar doesn't vanish.
    max_week_count = max(week_counts.values(), default=0)
    checkout_weeks = []
    for week_start in week_starts:
        count = week_counts[week_start]
        pct = round(count / max_week_count * 100) if max_week_count else 0
        if count and pct < 4:
            pct = 4
        checkout_weeks.append({
            "label": f"{week_start.strftime('%b')} {week_start.day}",
            "count": count,
            "pct": pct,
        })

    # Overdue: active checkouts already past their expected return date.
    overdue_checkout_count = session.query(ItemCheckout).filter(
        ItemCheckout.is_active.is_(True),
        ItemCheckout.expected_return_date.isnot(None),
        ItemCheckout.expected_return_date < today,
    ).count()

    # Inventory by status: proportions per item type. Keys are measured in
    # copies (that's what available/checked-out mean for key sets); the
    # others in items. Percentages are precomputed here so the template
    # only renders widths (divide-by-zero guarded when total is 0). The
    # unfilled remainder of a track is any other status (maintenance,
    # retired, ...).
    sign_assigned = session.query(Item).filter_by(type="Sign", status="assigned").count()
    key_copies_total = int(key_available_count) + int(key_checked_out_count)

    def status_segments(total, pairs):
        return [
            {
                "label": label,
                "cls": cls,
                "count": int(count),
                "pct": round((count / total) * 100, 1) if total else 0,
            }
            for label, cls, count in pairs
        ]

    inventory_status_rows = [
        {
            "name": "Lockboxes",
            "unit": "lockboxes",
            "total": lockbox_total,
            "segments": status_segments(lockbox_total, [
                ("Available", "seg-available", lockbox_available),
                ("Checked out", "seg-checked-out", lockbox_checked_out),
                ("Assigned", "seg-assigned", lockbox_assigned),
            ]),
        },
        {
            "name": "Keys",
            "unit": "copies",
            "total": key_copies_total,
            "segments": status_segments(key_copies_total, [
                ("Available", "seg-available", key_available_count),
                ("Checked out", "seg-checked-out", key_checked_out_count),
            ]),
        },
        {
            "name": "Signs",
            "unit": "signs",
            "total": sign_total,
            "segments": status_segments(sign_total, [
                ("Available", "seg-available", sign_available),
                ("Checked out", "seg-checked-out", sign_checked_out),
                ("Assigned", "seg-assigned", sign_assigned),
            ]),
        },
    ]

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
        # Analytics
        checkout_weeks=checkout_weeks,
        overdue_checkout_count=overdue_checkout_count,
        inventory_status_rows=inventory_status_rows,
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

    # All keys below the tenant's configured low-keys threshold.
    from utilities.database import get_tenant_settings
    low_keys_threshold = get_tenant_settings().low_keys_threshold
    all_keys_low = session.query(Item).filter(
        Item.type == "Key",
        Item.total_copies < low_keys_threshold
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
