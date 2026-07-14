"""API index, current-identity, and documentation endpoints."""

from flask import g, jsonify, render_template

from api import api_bp
from api.helpers import api_auth_required
from api.openapi import build_spec
from config import APP_VERSION


@api_bp.get("/")
def index():
    """Public API index — a quick orientation for anyone poking at the root."""
    return jsonify({
        "name": "KBM API",
        "version": "v1",
        "app_version": APP_VERSION,
        "documentation": "/api/v1/docs",
        "openapi": "/api/v1/openapi.json",
        "authentication": (
            "Create a token with POST /api/v1/auth/tokens {email, pin} on your "
            "company subdomain, then send it as 'Authorization: Bearer <token>'."
        ),
    })


@api_bp.get("/me")
@api_auth_required
def me():
    """Identify the token's user — handy for smoke-testing credentials."""
    user = g.api_user
    token = g.api_token
    return jsonify({
        "user": user.to_dict(),
        "token": token.to_dict(),
    })


@api_bp.get("/openapi.json")
def openapi_spec():
    return jsonify(build_spec())


@api_bp.get("/docs")
def docs():
    import re
    from markupsafe import Markup, escape

    spec = build_spec()
    # The OpenAPI description uses minimal markdown (**bold**, `code`).
    # Render it as HTML for the docs page; JSON consumers get it verbatim.
    text = str(escape(spec["info"]["description"]))
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return render_template("api_docs.html", spec=spec, intro_html=Markup(text))
