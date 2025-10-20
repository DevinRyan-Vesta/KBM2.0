"""
Accounts blueprint for account creation and management.
Handles company account signup and onboarding.
"""

from flask import Blueprint

accounts_bp = Blueprint('accounts', __name__)

from . import routes
