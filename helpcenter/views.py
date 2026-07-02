"""Built-in Help Center.

Every topic is a template under templates/help/. The topbar "?" button is
context-sensitive: `topic_for_endpoint()` maps the current page's endpoint to
the most relevant help topic, so users land on the page that explains what
they're looking at.
"""
from collections import OrderedDict

from flask import Blueprint, render_template, abort
from flask_login import login_required

help_bp = Blueprint("help", __name__, template_folder="../templates")


# slug -> metadata. Order controls the Help Center index and sidebar.
HELP_TOPICS = OrderedDict([
    ("getting-started", {"title": "Getting Started", "icon": "🚀",
                         "summary": "Log in, find your way around, and learn the basics."}),
    ("lockboxes", {"title": "Lockboxes", "icon": "🔒",
                   "summary": "Add lockboxes, manage codes, assign to properties, check in/out."}),
    ("keys", {"title": "Keys", "icon": "🔑",
              "summary": "Track key copies, hooks, checkouts, and master keys."}),
    ("signs", {"title": "Signs", "icon": "🪧",
               "summary": "Manage sign pieces, build assembled units, and track condition."}),
    ("checkout", {"title": "Check In / Out", "icon": "📝",
                  "summary": "The fast lane for scanning items in and out."}),
    ("receipts", {"title": "Receipts", "icon": "🧾",
                  "summary": "Find and print checkout receipts."}),
    ("audits", {"title": "Audits", "icon": "📋",
                "summary": "Run key audits, enter counts, and apply corrections."}),
    ("reports", {"title": "Reports & Exports", "icon": "📊",
                 "summary": "Overdue, upcoming, low-stock reports and CSV/Excel/PDF exports."}),
    ("calendar", {"title": "Calendar", "icon": "📅",
                  "summary": "See checkouts and expected returns on a month view."}),
    ("properties", {"title": "Properties & Units", "icon": "🏘️",
                    "summary": "Manage properties, units, and what's assigned to them."}),
    ("contacts", {"title": "Contacts", "icon": "👤",
                  "summary": "Track staff, contractors, tenants, and agents."}),
    ("smartlocks", {"title": "Smart Locks", "icon": "🔐",
                    "summary": "Track smart lock codes, locations, and photos."}),
    ("imports", {"title": "Importing Data", "icon": "📥",
                 "summary": "Bulk-import keys, lockboxes, signs, properties, and smart locks."}),
    ("search", {"title": "Search", "icon": "🔍",
                "summary": "Find anything fast with global search."}),
    ("users-roles", {"title": "Users & Roles", "icon": "👥",
                     "summary": "Add users, set PINs, understand permissions, review activity."}),
    ("settings", {"title": "Settings", "icon": "⚙️",
                  "summary": "Email notifications, thresholds, and receipt text."}),
])


# Endpoint-prefix -> topic slug, most specific first. Anything that doesn't
# match falls back to its blueprint, then to the Help index.
_ENDPOINT_PREFIX_MAP = [
    ("inventory.receipt", "receipts"),
    ("inventory.checkout_receipt", "receipts"),
    ("inventory.import_", "imports"),
    ("inventory.list_lockboxes", "lockboxes"),
    ("inventory.add_lockbox", "lockboxes"),
    ("inventory.lockbox", "lockboxes"),
    ("inventory.list_keys", "keys"),
    ("inventory.add_key", "keys"),
    ("inventory.key", "keys"),
    ("inventory.list_signs", "signs"),
    ("inventory.add_sign", "signs"),
    ("inventory.build_sign", "signs"),
    ("inventory.sign", "signs"),
    ("properties.import_", "imports"),
    ("smartlocks.import_", "imports"),
    ("main.reports", "reports"),
    ("auth.profile", "users-roles"),
    ("auth.list_users", "users-roles"),
    ("auth.create_user", "users-roles"),
    ("auth.edit_user", "users-roles"),
    ("auth.activity_logs", "users-roles"),
    ("auth.export_activity_logs", "users-roles"),
]

_BLUEPRINT_MAP = {
    "main": "getting-started",
    "calendar": "calendar",
    "checkout": "checkout",
    "audits": "audits",
    "exports": "reports",
    "properties": "properties",
    "contacts": "contacts",
    "smartlocks": "smartlocks",
    "search": "search",
    "settings": "settings",
    "auth": "users-roles",
}


def topic_for_endpoint(endpoint: str | None) -> str | None:
    """Return the help topic slug most relevant to a Flask endpoint."""
    if not endpoint:
        return None
    for prefix, slug in _ENDPOINT_PREFIX_MAP:
        if endpoint.startswith(prefix):
            return slug
    blueprint = endpoint.split(".", 1)[0]
    return _BLUEPRINT_MAP.get(blueprint)


@help_bp.route("/", methods=["GET"])
@login_required
def index():
    return render_template("help/index.html", topics=HELP_TOPICS)


@help_bp.route("/<slug>", methods=["GET"])
@login_required
def topic(slug: str):
    if slug not in HELP_TOPICS:
        abort(404)
    meta = HELP_TOPICS[slug]
    return render_template(f"help/{slug}.html", topics=HELP_TOPICS,
                           slug=slug, meta=meta)
