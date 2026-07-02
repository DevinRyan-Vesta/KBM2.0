# calendarview/views.py
# Month-grid calendar of checkout activity: expected returns due per day,
# items checked out per day, and a highlighted list of overdue returns.
# (Package is named "calendarview" to avoid shadowing the stdlib calendar
# module, but the blueprint/endpoint name stays "calendar".)
import calendar as stdlib_calendar
from datetime import date, datetime

from flask import Blueprint, render_template, redirect, request, url_for
from flask_login import login_required
from middleware.tenant_middleware import tenant_required
from utilities.database import Item, ItemCheckout
from utilities.tenant_helpers import tenant_query

calendar_bp = Blueprint(
    "calendar",
    __name__,
    template_folder="../templates",
    static_folder="../static"
)


@calendar_bp.get("/")
@login_required
@tenant_required
def calendar_view():
    """Month view of checkout activity (?year=YYYY&month=MM, defaults to now)."""
    today = date.today()

    # Parse the requested month; anything unparseable or out of range just
    # redirects back to the current month rather than erroring.
    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
    except (TypeError, ValueError):
        return redirect(url_for("calendar.calendar_view"))
    if not (1 <= month <= 12) or not (1 <= year <= 9999):
        return redirect(url_for("calendar.calendar_view"))

    # Neighbouring months for the prev/next buttons
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    # Datetime bounds of the displayed month (columns are DateTime)
    month_start = datetime(year, month, 1)
    if year == 9999 and month == 12:
        month_end = datetime(9999, 12, 31, 23, 59, 59)
    else:
        month_end = datetime(next_year, next_month, 1)

    # Expected returns due this month (still-active checkouts only)
    due_rows = tenant_query(ItemCheckout).filter(
        ItemCheckout.is_active == True,
        ItemCheckout.expected_return_date >= month_start,
        ItemCheckout.expected_return_date < month_end,
    ).order_by(ItemCheckout.expected_return_date).all()

    # Items checked out this month (regardless of whether they're back yet)
    out_rows = tenant_query(ItemCheckout).filter(
        ItemCheckout.checked_out_at >= month_start,
        ItemCheckout.checked_out_at < month_end,
    ).order_by(ItemCheckout.checked_out_at).all()

    # Group by calendar day
    due_by_day = {}
    for co in due_rows:
        due_by_day.setdefault(co.expected_return_date.date(), []).append(co)
    out_by_day = {}
    for co in out_rows:
        out_by_day.setdefault(co.checked_out_at.date(), []).append(co)

    # Everything overdue right now (any month) for the list above the grid
    today_start = datetime(today.year, today.month, today.day)
    overdue = tenant_query(ItemCheckout).filter(
        ItemCheckout.is_active == True,
        ItemCheckout.expected_return_date != None,  # noqa: E711
        ItemCheckout.expected_return_date < today_start,
    ).order_by(ItemCheckout.expected_return_date).all()

    # Build the week rows; monthcalendar pads other-month days with 0
    weeks = []
    for week in stdlib_calendar.monthcalendar(year, month):
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(None)  # day belongs to the previous/next month
                continue
            day_date = date(year, month, day_num)
            row.append({
                "day": day_num,
                "date": day_date,
                "is_today": day_date == today,
                "due": due_by_day.get(day_date, []),
                "out": out_by_day.get(day_date, []),
                # Active checkouts due before today are overdue on their due day
                "is_overdue": day_date < today and bool(due_by_day.get(day_date)),
            })
        weeks.append(row)

    return render_template(
        "calendar.html",
        year=year,
        month=month,
        month_name=stdlib_calendar.month_name[month],
        weeks=weeks,
        weekday_names=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        overdue=overdue,
        today=today,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
    )
