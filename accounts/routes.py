"""
Account signup and management routes.
"""

import logging
import re

from flask import render_template, request, redirect, url_for, flash, current_app
from . import accounts_bp
from utilities.extensions import limiter
from utilities.master_database import master_db, Account, MasterUser
from utilities.tenant_manager import tenant_manager
from middleware.tenant_middleware import root_domain_only

log = logging.getLogger(__name__)


@accounts_bp.route('/signup', methods=['GET', 'POST'])
@root_domain_only
@limiter.limit("3 per hour; 10 per day", methods=["POST"])
def signup():
    """
    Company account signup form.
    Creates a new account, database, and first admin user.

    New accounts land as status='pending' and require app-admin approval
    before they can be used. This means even if a bot squeaks past the
    honeypot + rate limit, the resulting account is unusable until a
    human approves it.
    """
    if request.method == 'GET':
        return render_template('accounts/signup.html')

    # ------------------------------------------------------------------
    # Bot prevention layer 1: honeypot.
    # The signup form has a hidden 'website' field that's invisible to
    # humans (CSS-hidden). Bots that auto-fill every input will populate
    # it. If we see a value, drop the request and pretend it succeeded
    # so the bot doesn't retry.
    # ------------------------------------------------------------------
    if request.form.get('website', '').strip():
        log.info("signup blocked by honeypot from %s", request.remote_addr)
        flash('Account created. Awaiting administrator approval.', 'success')
        return redirect(url_for('accounts.signup'))

    # Bot prevention layer 2 — rate limit — is applied via the
    # @limiter.limit decorator on this route (3/hour, 10/day per IP).

    # Process signup form
    subdomain = request.form.get('subdomain', '').lower().strip()
    company_name = request.form.get('company_name', '').strip()
    admin_name = request.form.get('admin_name', '').strip()
    admin_email = request.form.get('admin_email', '').strip()
    admin_pin = request.form.get('admin_pin', '').strip()
    admin_pin_confirm = request.form.get('admin_pin_confirm', '').strip()

    # Validation
    errors = []

    if not subdomain:
        errors.append("Subdomain is required")
    else:
        is_valid, error_msg = Account.validate_subdomain(subdomain)
        if not is_valid:
            errors.append(error_msg)

    if not company_name:
        errors.append("Company name is required")
    elif len(company_name) < 2:
        errors.append("Company name must be at least 2 characters")

    if not admin_name:
        errors.append("Admin name is required")
    elif len(admin_name) < 2:
        errors.append("Admin name must be at least 2 characters")

    if not admin_email:
        errors.append("Admin email is required")
    elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', admin_email):
        errors.append("Invalid email format")

    if not admin_pin:
        errors.append("PIN is required")
    elif len(admin_pin) < 4:
        errors.append("PIN must be at least 4 characters")
    elif admin_pin != admin_pin_confirm:
        errors.append("PINs do not match")

    if errors:
        for error in errors:
            flash(error, 'error')
        return render_template('accounts/signup.html',
                             subdomain=subdomain,
                             company_name=company_name,
                             admin_name=admin_name,
                             admin_email=admin_email)

    try:
        # New accounts land as pending — an app admin must approve before
        # the subdomain becomes usable. Until then, the tenant middleware
        # blocks logins (returns 403) and the account shows up in the
        # "Pending Approval" filter on the admin dashboard.
        account = Account(
            subdomain=subdomain,
            company_name=company_name,
            status='pending'
        )

        # Get database path
        db_path = tenant_manager.get_tenant_database_path(account)
        account.database_path = str(db_path)

        master_db.session.add(account)
        master_db.session.flush()  # Get account ID

        # Create tenant database
        tenant_manager.create_tenant_database(account)

        # Create first admin user
        admin_user = MasterUser(
            account_id=account.id,
            name=admin_name,
            email=admin_email,
            role='admin'
        )
        admin_user.set_pin(admin_pin)

        master_db.session.add(admin_user)
        master_db.session.commit()

        # Don't redirect to the subdomain — the account isn't active yet.
        # Show a confirmation page so the user knows what to expect.
        return render_template(
            'accounts/signup_pending.html',
            company_name=company_name,
            subdomain=subdomain,
            admin_email=admin_email,
        )

    except Exception as e:
        master_db.session.rollback()
        current_app.logger.error(f"Error creating account: {e}")
        flash(f'Error creating account: {str(e)}', 'error')
        return render_template('accounts/signup.html',
                             subdomain=subdomain,
                             company_name=company_name,
                             admin_name=admin_name,
                             admin_email=admin_email)


@accounts_bp.route('/check-subdomain')
@root_domain_only
def check_subdomain():
    """
    AJAX endpoint to check if subdomain is available.
    Returns JSON: {"available": true/false, "message": "..."}
    """
    subdomain = request.args.get('subdomain', '').lower().strip()

    if not subdomain:
        return {"available": False, "message": "Subdomain is required"}

    is_valid, message = Account.validate_subdomain(subdomain)

    return {
        "available": is_valid,
        "message": message if not is_valid else "This subdomain is available"
    }
