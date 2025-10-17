from flask import request, Blueprint, render_template, redirect, url_for, flash, abort
from flask_login import login_user, logout_user, login_required, current_user
from typing import Dict, Optional
from utilities.database import db, User, ActivityLog, log_activity

# Define the blueprint HERE. Do NOT import another auth_bp from elsewhere.
auth_bp = Blueprint(
    "auth",
    __name__,
    template_folder="../templates",
    static_folder="../static"
)
ALLOWED_ROLES = ["admin", "user", "staff", "agent"]


def _require_admin():
    if getattr(current_user, "role", "").lower() != "admin":
        abort(403)


def _clean_pin(pin: Optional[str]) -> Optional[str]:
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
) -> Dict[str, str]:
    errors: Dict[str, str] = {}

    if not name:
        errors["name"] = "Name is required."
    if not email:
        errors["email"] = "Email is required."

    normalized_pin = _clean_pin(pin)
    if require_pin and not normalized_pin:
        errors["pin"] = "PIN is required."
    elif normalized_pin and (len(normalized_pin) < 4 or not normalized_pin.isdigit()):
        errors["pin"] = "PIN must be numeric and at least 4 digits."

    if role is not None:
        if role.lower() not in [r.lower() for r in ALLOWED_ROLES]:
            errors["role"] = "Select a valid role."

    if email:
        existing_email = User.query.filter(
            db.func.lower(User.email) == email.lower(),
            User.id != (user_id or 0),
        ).first()
        if existing_email:
            errors["email"] = "Email already exists."

    if name:
        existing_name = User.query.filter(
            db.func.lower(User.name) == name.lower(),
            User.id != (user_id or 0),
        ).first()
        if existing_name:
            errors["name"] = "Name already exists."

    return errors

@auth_bp.get("/login-shortcut")
def login_shortcut():
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("inventory.list_lockboxes"))
    return render_template("login.html")

@auth_bp.route("/login", methods=["POST"])
def login_post():
    try:
        pin = (request.form.get("pin") or "").strip()
        remember = bool(request.form.get("remember", False))

        if not pin:
            flash("Enter your PIN.", "error")
            return redirect(url_for("auth.login"))

        # Find active users whose hashed PIN matches
        candidates = []
        for u in User.query.filter_by(is_active=True).all():
            if u.check_pin(pin):
                candidates.append(u)

        if not candidates:
            flash("Invalid PIN.", "error")
            return redirect(url_for("auth.login"))

        if len(candidates) > 1:
            # Safety: enforce unique PINs
            flash("PIN is not unique. Ask an admin to assign a unique PIN.", "error")
            return redirect(url_for("auth.login"))

        user = candidates[0]
        login_user(user, remember=remember)
        log_activity(
            "auth_login",
            user=user,
            summary="User signed in",
            meta={"remember": bool(remember)},
            commit=True,
        )
        return redirect(url_for("main.home"))

    except Exception as e:
        db.session.rollback()
        # Optional: log/print for dev
        print("Login error:", e)
        flash("Something went wrong signing you in. Please try again.", "error")
        return redirect(url_for("auth.login"))

@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    user = current_user if current_user.is_authenticated else None
    try:
        logout_user()
    except Exception as e:
        print("Logout error:", e)  # Optional logging
        flash("An error occurred during logout. Please try again.", "error")
        return redirect(url_for("auth.login"))

    if user:
        log_activity(
            "auth_logout",
            user=user,
            summary="User signed out",
            commit=True,
        )
    return redirect(url_for("auth.login"))


@auth_bp.route("/users", methods=["GET"])
@login_required
def list_users():
    _require_admin()
    users = User.query.order_by(User.name.asc()).all()
    return render_template("users.html", users=users, allowed_roles=ALLOWED_ROLES)


@auth_bp.route("/users/new", methods=["GET", "POST"])
@login_required
def create_user():
    _require_admin()
    errors = {}
    form_values = {
        "name": "",
        "email": "",
        "role": "user",
        "is_active": "1",
    }

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        pin = (request.form.get("pin") or "").strip()
        role = (request.form.get("role") or "user").strip().lower()

        errors = _validate_user_fields(name=name, email=email, pin=pin, role=role, require_pin=True)

        form_values.update({"name": name, "email": email, "role": role})

        if not errors:
            new_user = User(
                name=name,
                email=email,
                role=role,
                is_active=True,
            )
            new_user.set_pin(pin)
            db.session.add(new_user)
            db.session.flush()
            log_activity(
                "user_created",
                user=current_user,
                target=new_user,
                summary=f"Created user {name}",
                meta={"email": email, "role": role},
                commit=False,
            )
            db.session.commit()
            flash(f"User {name} created.", "success")
            return redirect(url_for("auth.list_users"))

        for field, message in errors.items():
            flash(message, "error")

    return render_template(
        "user_form.html",
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
def edit_user(user_id: int):
    _require_admin()
    user = User.query.get_or_404(user_id)
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
        )

        form_values.update(
            {
                "name": name,
                "email": email,
                "role": role,
                "is_active": "1" if is_active else "0",
            }
        )

        if not errors:
            before = {
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
            }

            user.name = name
            user.email = email
            user.role = role
            user.is_active = is_active

            pin_changed = False
            clean_pin = _clean_pin(pin)
            if clean_pin:
                user.set_pin(clean_pin)
                pin_changed = True

            changes = {}
            for key, old_value in before.items():
                new_value = getattr(user, key)
                if old_value != new_value:
                    changes[key] = {"from": old_value, "to": new_value}
            if pin_changed:
                changes["pin"] = {"from": "****", "to": "updated"}

            if changes:
                log_activity(
                    "user_updated",
                    user=current_user,
                    target=user,
                    summary=f"Updated user {user.name}",
                    meta={"changes": changes},
                    commit=False,
                )

            db.session.commit()
            flash(f"User {user.name} updated.", "success")
            return redirect(url_for("auth.list_users"))

        for field, message in errors.items():
            flash(message, "error")

    return render_template(
        "user_form.html",
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
def delete_user(user_id: int):
    _require_admin()
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("You cannot remove your own account.", "error")
        return redirect(url_for("auth.list_users"))

    info = {"name": user.name, "email": user.email, "role": user.role}
    db.session.delete(user)
    log_activity(
        "user_deleted",
        user=current_user,
        target_type="User",
        target_id=user_id,
        summary=f"Removed user {info['name']}",
        meta=info,
        commit=False,
    )
    db.session.commit()
    flash(f"User {info['name']} removed.", "success")
    return redirect(url_for("auth.list_users"))


@auth_bp.route("/activity-logs", methods=["GET"])
@login_required
def activity_logs():
    _require_admin()
    logs = (
        ActivityLog.query
        .order_by(ActivityLog.created_at.desc())
        .limit(200)
        .all()
    )
    return render_template("activity_logs.html", logs=logs)


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
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
        )

        form_values.update({"name": name, "email": email})

        if not errors:
            before = {
                "name": user.name,
                "email": user.email,
            }
            user.name = name
            user.email = email

            pin_changed = False
            clean_pin = _clean_pin(pin)
            if clean_pin:
                user.set_pin(clean_pin)
                pin_changed = True

            changes = {}
            for key, old_value in before.items():
                new_value = getattr(user, key)
                if old_value != new_value:
                    changes[key] = {"from": old_value, "to": new_value}
            if pin_changed:
                changes["pin"] = {"from": "****", "to": "updated"}

            if changes:
                log_activity(
                    "user_profile_updated",
                    user=user,
                    target=user,
                    summary="User updated profile",
                    meta={"changes": changes},
                    commit=False,
                )

            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("auth.profile"))

        for field, message in errors.items():
            flash(message, "error")

    return render_template(
        "user_form.html",
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
