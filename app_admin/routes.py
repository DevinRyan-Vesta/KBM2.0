"""
App admin routes for system-level administration.
"""

from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from . import app_admin_bp
from utilities.master_database import master_db, Account, MasterUser
from utilities.tenant_manager import tenant_manager
from middleware.tenant_middleware import app_admin_required, root_domain_only


@app_admin_bp.route('/admin/dashboard')
@login_required
@app_admin_required
@root_domain_only
def dashboard():
    """
    App admin dashboard showing overview of all accounts.
    """
    accounts = Account.query.order_by(Account.created_at.desc()).all()

    # Gather statistics
    total_accounts = len(accounts)
    active_accounts = sum(1 for a in accounts if a.status == 'active')
    total_users = MasterUser.query.filter(MasterUser.account_id.isnot(None)).count()

    stats = {
        'total_accounts': total_accounts,
        'active_accounts': active_accounts,
        'suspended_accounts': sum(1 for a in accounts if a.status == 'suspended'),
        'total_users': total_users,
    }

    return render_template('app_admin/dashboard.html',
                         accounts=accounts,
                         stats=stats)


@app_admin_bp.route('/admin/accounts')
@login_required
@app_admin_required
@root_domain_only
def list_accounts():
    """
    List all accounts with filtering and search.
    """
    # Get filter parameters
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('q', '').strip()

    # Base query
    query = Account.query

    # Apply filters
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)

    if search_query:
        query = query.filter(
            master_db.or_(
                Account.company_name.ilike(f'%{search_query}%'),
                Account.subdomain.ilike(f'%{search_query}%')
            )
        )

    accounts = query.order_by(Account.created_at.desc()).all()

    return render_template('app_admin/accounts.html',
                         accounts=accounts,
                         status_filter=status_filter,
                         search_query=search_query)


@app_admin_bp.route('/admin/accounts/<int:account_id>')
@login_required
@app_admin_required
@root_domain_only
def view_account(account_id):
    """
    View details of a specific account.
    """
    account = Account.query.get_or_404(account_id)
    users = MasterUser.query.filter_by(account_id=account.id).all()

    # Get base domain for building subdomain URLs
    base_domain = current_app.config.get('BASE_DOMAIN', 'localhost:5000')

    # Determine protocol based on domain
    protocol = 'http' if 'localhost' in base_domain else 'https'

    return render_template('app_admin/account_detail.html',
                         account=account,
                         users=users,
                         base_domain=base_domain,
                         protocol=protocol)


@app_admin_bp.route('/admin/accounts/<int:account_id>/update-status', methods=['POST'])
@login_required
@app_admin_required
@root_domain_only
def update_account_status(account_id):
    """
    Update account status (activate/suspend/delete).
    """
    account = Account.query.get_or_404(account_id)
    new_status = request.form.get('status')

    if new_status not in ['active', 'suspended', 'deleted']:
        flash('Invalid status', 'error')
        return redirect(url_for('app_admin.view_account', account_id=account_id))

    old_status = account.status
    account.status = new_status

    master_db.session.commit()

    flash(f'Account status updated from {old_status} to {new_status}', 'success')
    return redirect(url_for('app_admin.view_account', account_id=account_id))


@app_admin_bp.route('/admin/accounts/<int:account_id>/delete', methods=['POST'])
@login_required
@app_admin_required
@root_domain_only
def delete_account(account_id):
    """
    Permanently delete an account and its database (use with extreme caution!).
    """
    account = Account.query.get_or_404(account_id)

    # Require confirmation
    confirmation = request.form.get('confirmation', '').strip()
    if confirmation != account.subdomain:
        flash('Incorrect confirmation. Account not deleted.', 'error')
        return redirect(url_for('app_admin.view_account', account_id=account_id))

    subdomain = account.subdomain
    company_name = account.company_name

    try:
        # Delete tenant database file
        tenant_manager.delete_tenant_database(account)

        # Delete all users in this account
        MasterUser.query.filter_by(account_id=account.id).delete()

        # Delete account record
        master_db.session.delete(account)
        master_db.session.commit()

        flash(f'Account "{company_name}" ({subdomain}) has been permanently deleted.', 'success')
        return redirect(url_for('app_admin.list_accounts'))

    except Exception as e:
        master_db.session.rollback()
        flash(f'Error deleting account: {str(e)}', 'error')
        return redirect(url_for('app_admin.view_account', account_id=account_id))


@app_admin_bp.route('/admin/accounts/<int:account_id>/stats')
@login_required
@app_admin_required
@root_domain_only
def account_stats(account_id):
    """
    Get statistics for a specific account (AJAX endpoint).
    """
    account = Account.query.get_or_404(account_id)

    try:
        # Get tenant database session
        session = tenant_manager.get_tenant_session(account)

        # Import models to query
        from utilities.database import Item, ItemCheckout, Contact, Property

        stats = {
            'users': MasterUser.query.filter_by(account_id=account.id).count(),
            'items': session.query(Item).count(),
            'active_checkouts': session.query(ItemCheckout).filter_by(is_active=True).count(),
            'contacts': session.query(Contact).count(),
            'properties': session.query(Property).count(),
        }

        return jsonify(stats)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app_admin_bp.route('/admin/app-admins')
@login_required
@app_admin_required
@root_domain_only
def list_app_admins():
    """
    List all app-level administrators.
    """
    app_admins = MasterUser.query.filter_by(role='app_admin').order_by(MasterUser.name.asc()).all()

    return render_template('app_admin/app_admins.html', app_admins=app_admins)


@app_admin_bp.route('/admin/app-admins/new', methods=['GET', 'POST'])
@login_required
@app_admin_required
@root_domain_only
def create_app_admin():
    """
    Create a new app-level administrator.
    """
    if request.method == 'GET':
        return render_template('app_admin/app_admin_form.html')

    # Process form
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    pin = request.form.get('pin', '').strip()

    errors = []

    if not name:
        errors.append("Name is required")
    if not email:
        errors.append("Email is required")
    if not pin or len(pin) < 4:
        errors.append("PIN must be at least 4 characters")

    # Check for duplicate email
    if email:
        existing = MasterUser.query.filter_by(email=email).first()
        if existing:
            errors.append("Email already exists")

    if errors:
        for error in errors:
            flash(error, 'error')
        return render_template('app_admin/app_admin_form.html',
                             name=name,
                             email=email)

    # Create app admin
    admin = MasterUser(
        account_id=None,  # App admins don't belong to a tenant
        name=name,
        email=email,
        role='app_admin',
        is_active=True
    )
    admin.set_pin(pin)

    master_db.session.add(admin)
    master_db.session.commit()

    flash(f'App admin {name} created successfully', 'success')
    return redirect(url_for('app_admin.list_app_admins'))
