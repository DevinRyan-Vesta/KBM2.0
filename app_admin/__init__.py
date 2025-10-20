"""
App Admin blueprint for system-level administration.
Only accessible to app_admin users.
"""

from flask import Blueprint

app_admin_bp = Blueprint('app_admin', __name__)

from . import routes
