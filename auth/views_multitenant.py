"""
Multi-tenant authentication views.
Handles login/logout for both tenant users and app admins.
"""

from flask import request, Blueprint, render_template, redirect, url_for, flash, abort, g
from flask_login import login_user, logout_user, login_required, current_user
from typing import Dict, Optional
from utilities.master_database import master_db, MasterUser
from utilities.tenant_manager import tenant_manager
from middleware.tenant_middleware import tenant_required, app_admin_required
from datetime import datetime, UTC

# Rate limiting helper
def apply_rate_limit(func):
    """Apply rate limiting to a view function if available"""
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
        import os

        # Only apply if rate limiting is enabled
        if os.getenv('RATELIMIT_ENABLED', 'false').lower() in ('true', '1', 'yes'):
            # Create a simple rate limiter for this view
            from functools import wraps

            @wraps(func)
            def wrapper(*args, **kwargs):
                # Simple in-memory rate limiting could be added here
                # For now, just pass through
                return func(*args, **kwargs)
            return wrapper
    except ImportError:
        pass

    return func

# Define the blueprint
auth_bp = Blueprint(
    "auth",
    __name__,
    template_folder="../templates",
    static_folder="../static"
)

ALLOWED_ROLES = ["admin", "user", "staff", "agent"]


def _require_admin():
    """Require current user to be an admin (tenant or app)."""
    if getattr(current_user, "role", "").lower() not in ["admin", "app_admin"]:
        abort(403)


def _clean_pin(pin: Optional[str]) -> Optional[str]:
    """Clean and normalize PIN input."""
    if pin is None:
        return None
    pin = pin.strip()
    return pin or None


def _validate_user_fields(
    *,
    name: str,
    email: str,
    pin: Optional[str],
    role: Optional[str] = None,
    require_pin: bool = False,
    user_id: Optional[int] = None,
    account_id: Optional[int] = None,
) -> Dict[str, str]:
    """Validate user form fields."""
    errors: Dict[str, str] = {}

    if not name:
        errors["name"] = "Name is required."
    if not email:
        errors["email"] = "Email is required."

    normalized_pin = _clean_pin(pin)
    if require_pin and not normalized_pin:
        errors["pin"] = "PIN is required."
    elif normalized_pin and len(normalized_pin) < 4:
        errors["pin"] = "PIN must be at least 4 characters."

    if role is not None:
        if role.lower() not in [r.lower() for r in ALLOWED_ROLES] + ["app_admin"]:
            errors["role"] = "Select a valid role."

    # Check email uniqueness within account
    if email and account_id:
        existing_email = MasterUser.query.filter(
            master_db.func.lower(MasterUser.email) == email.lower(),
            MasterUser.account_id == account_id,
            MasterUser.id != (user_id or 0),
        ).first()
        if existing_email:
            errors["email"] = "Email already exists in this account."

    return errors


@auth_bp.get("/login-shortcut")
def login_shortcut():
    """Redirect to login page."""
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET"])
def login():
    """Display login form."""
    if current_user.is_authenticated:
        # Redirect based on user role
        if current_user.role == "app_admin":
            return redirect(url_for("app_admin.dashboard"))
        return redirect(url_for("main.home"))

    # Check if we're on a tenant subdomain
    is_tenant = tenant_manager.get_current_tenant() is not None

    return render_template("auth/login.html", is_tenant=is_tenant)


@auth_bp.route("/login", methods=["POST"])
def login_post():
    """Handle login form submission."""
    try:
        pin = (request.form.get("pin") or "").strip()
        remember = bool(request.form.get("remember", False))

        if not pin:
            flash("Enter your PIN.", "error")
            return redirect(url_for("auth.login"))

        # Get current tenant (if any)
        tenant = tenant_manager.get_current_tenant()

        # Find users whose PIN matches
        if tenant:
            # Tenant login - only check users from this account
            candidates = []
            for u in MasterUser.query.filter_by(
                account_id=tenant.id,
                is_active=True
            ).all():
                if u.check_pin(pin):
                    candidates.append(u)
        else:
            # Root domain login - only app admins
            candidates = []
            for u in MasterUser.query.filter_by(
                role='app_admin',
                is_active=True
            ).all():
                if u.check_pin(pin):
                    candidates.append(u)

        if not candidates:
            flash("Invalid PIN.", "error")
            return redirect(url_for("auth.login"))

        if len(candidates) > 1:
            # Safety: enforce unique PINs within account
            flash("PIN is not unique. Ask an admin to assign a unique PIN.", "error")
            return redirect(url_for("auth.login"))

        user = candidates[0]

        # Update last login
        user.last_login_at = datetime.now(UTC).replace(tzinfo=None)

        login_user(user, remember=remember)
        master_db.session.commit()

        # Redirect based on role
        if user.role == "app_admin":
            return redirect(url_for("app_admin.dashboard"))
        return redirect(url_for("main.home"))

    except Exception as e:
        master_db.session.rollback()
        print("Login error:", e)
        flash("Something went wrong signing you in. Please try again.", "error")
        return redirect(url_for("auth.login"))


@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    """Handle user logout."""
    try:
        logout_user()
        flash("You have been signed out.", "success")
    except Exception as e:
        print("Logout error:", e)
        flash("An error occurred during logout. Please try again.", "error")

    return redirect(url_for("auth.login"))


@auth_bp.route("/users", methods=["GET"])
@login_required
@tenant_required
def list_users():
    """List all users in the current tenant account."""
    _require_admin()

    tenant = tenant_manager.get_current_tenant()
    users = MasterUser.query.filter_by(account_id=tenant.id).order_by(MasterUser.name.asc()).all()

    return render_template("auth/users.html", users=users, allowed_roles=ALLOWED_ROLES)


@auth_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@tenant_required
def create_user():
    """Create a new user in the current tenant account."""
    _require_admin()

    tenant = tenant_manager.get_current_tenant()
    errors = {}
    form_values = {
        "name": "",
        "email": "",
        "role": "user",
    }

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        pin = (request.form.get("pin") or "").strip()
        role = (request.form.get("role") or "user").strip().lower()

        errors = _validate_user_fields(
            name=name,
            email=email,
            pin=pin,
            role=role,
            require_pin=True,
            account_id=tenant.id
        )

        form_values.update({"name": name, "email": email, "role": role})

        if not errors:
            new_user = MasterUser(
                account_id=tenant.id,
                name=name,
                email=email,
                role=role,
                is_active=True,
            )
            new_user.set_pin(pin)
            master_db.session.add(new_user)
            master_db.session.commit()

            flash(f"User {name} created.", "success")
            return redirect(url_for("auth.list_users"))

        for field, message in errors.items():
            flash(message, "error")

    return render_template(
        "auth/user_form.html",
        page_title="Add User",
        page_heading="Add User",
        submit_label="Create User",
        cancel_url=url_for("auth.list_users"),
        allowed_roles=ALLOWED_ROLES,
        show_role=True,
        show_active_toggle=False,
        user=None,
        form_values=form_values,
        errors=errors,
    )


@auth_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@tenant_required
def edit_user(user_id: int):
    """Edit a user in the current tenant account."""
    _require_admin()

    tenant = tenant_manager.get_current_tenant()
    user = MasterUser.query.filter_by(id=user_id, account_id=tenant.id).first_or_404()

    errors = {}
    form_values = {
        "name": user.name or "",
        "email": user.email or "",
        "role": user.role or "user",
        "is_active": "1" if user.is_active else "0",
    }

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        pin = (request.form.get("pin") or "").strip()
        role = (request.form.get("role") or user.role).strip().lower()
        is_active = request.form.get("is_active", "1") == "1"

        errors = _validate_user_fields(
            name=name,
            email=email,
            pin=pin,
            role=role,
            require_pin=False,
            user_id=user.id,
            account_id=tenant.id
        )

        form_values.update({
            "name": name,
            "email": email,
            "role": role,
            "is_active": "1" if is_active else "0",
        })

        if not errors:
            user.name = name
            user.email = email
            user.role = role
            user.is_active = is_active

            clean_pin = _clean_pin(pin)
            if clean_pin:
                user.set_pin(clean_pin)

            master_db.session.commit()
            flash(f"User {user.name} updated.", "success")
            return redirect(url_for("auth.list_users"))

        for field, message in errors.items():
            flash(message, "error")

    return render_template(
        "auth/user_form.html",
        page_title="Edit User",
        page_heading=f"Edit {user.name}",
        submit_label="Save Changes",
        cancel_url=url_for("auth.list_users"),
        allowed_roles=ALLOWED_ROLES,
        show_role=True,
        show_active_toggle=True,
        user=user,
        form_values=form_values,
        errors=errors,
    )


@auth_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@tenant_required
def delete_user(user_id: int):
    """Delete a user from the current tenant account."""
    _require_admin()

    if user_id == current_user.id:
        flash("You cannot remove your own account.", "error")
        return redirect(url_for("auth.list_users"))

    tenant = tenant_manager.get_current_tenant()
    user = MasterUser.query.filter_by(id=user_id, account_id=tenant.id).first_or_404()

    user_name = user.name
    master_db.session.delete(user)
    master_db.session.commit()

    flash(f"User {user_name} removed.", "success")
    return redirect(url_for("auth.list_users"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """User profile page."""
    user = current_user
    errors = {}
    form_values = {
        "name": user.name or "",
        "email": user.email or "",
    }

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        pin = (request.form.get("pin") or "").strip()

        errors = _validate_user_fields(
            name=name,
            email=email,
            pin=pin,
            require_pin=False,
            user_id=user.id,
            account_id=user.account_id
        )

        form_values.update({"name": name, "email": email})

        if not errors:
            user.name = name
            user.email = email

            clean_pin = _clean_pin(pin)
            if clean_pin:
                user.set_pin(clean_pin)

            master_db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("auth.profile"))

        for field, message in errors.items():
            flash(message, "error")

    return render_template(
        "auth/user_form.html",
        page_title="My Profile",
        page_heading="Your Profile",
        submit_label="Save Changes",
        cancel_url=url_for("main.home"),
        allowed_roles=ALLOWED_ROLES,
        show_role=False,
        show_active_toggle=False,
        user=user,
        form_values=form_values,
        errors=errors,
    )


@auth_bp.route("/activity-logs", methods=["GET"])
@login_required
@tenant_required
def activity_logs():
    """Activity logs page for tenant."""
    _require_admin()
    
    from utilities.tenant_helpers import tenant_query
    from utilities.database import ActivityLog
    
    logs = (
        tenant_query(ActivityLog)
        .order_by(ActivityLog.created_at.desc())
        .limit(200)
        .all()
    )
    return render_template("activity_logs.html", logs=logs)
