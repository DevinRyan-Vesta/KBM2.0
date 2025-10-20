from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required
from sqlalchemy import or_, func

from utilities.database import db, Contact, Item, ItemCheckout, User

CONTACT_TYPES = ["staff", "contractor", "tenant", "agent"]

contacts_bp = Blueprint(
    "contacts",
    __name__,
    template_folder="../templates",
    static_folder="../static"
)


def _get_contact_or_404(contact_id: int) -> Contact:
    contact = db.session.get(Contact, contact_id)
    if contact is None:
        abort(404)
    return contact


def _get_available_staff_users(include_user_id: int | None = None) -> list[User]:
    users = User.query.order_by(User.name.asc()).all()
    available: list[User] = []
    for user in users:
        if user.contact_profile is None or (include_user_id is not None and user.id == include_user_id):
            available.append(user)
    return available


@contacts_bp.route("/", methods=["GET"])
@login_required
def list_contacts():
    q = (request.args.get("q") or "").strip()
    query = Contact.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Contact.name.ilike(like),
                Contact.email.ilike(like),
                Contact.company.ilike(like),
                Contact.phone.ilike(like),
            )
        )
    contacts = query.order_by(Contact.name.asc()).all()
    return render_template(
        "contacts.html",
        contacts=contacts,
        q=q,
        contact_types=CONTACT_TYPES,
    )


@contacts_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_contact():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        contact_type = (request.form.get("contact_type") or "").strip().lower()
        company = (request.form.get("company") or "").strip() or None
        email = (request.form.get("email") or "").strip() or None
        phone = (request.form.get("phone") or "").strip() or None
        notes = (request.form.get("notes") or "").strip() or None
        user_id_str = (request.form.get("user_id") or "").strip()

        errors: list[str] = []

        if not name:
            errors.append("Name is required.")
        if contact_type not in CONTACT_TYPES:
            errors.append("Select a valid contact type.")

        staff_user = None
        if contact_type == "staff" and user_id_str:
            try:
                user_id = int(user_id_str)
                staff_user = db.session.get(User, user_id)
            except ValueError:
                staff_user = None
            if staff_user is None:
                errors.append("Selected staff user could not be found.")
            elif staff_user.contact_profile is not None:
                errors.append("That user already has a contact profile.")

        if errors:
            for message in errors:
                flash(message, "error")
            return redirect(url_for("contacts.create_contact"))

        contact = Contact(
            name=name,
            contact_type=contact_type,
            company=company,
            email=email,
            phone=phone,
            notes=notes,
            user=staff_user,
        )
        db.session.add(contact)
        db.session.commit()
        flash("Contact created.", "success")
        return redirect(url_for("contacts.list_contacts"))

    staff_users = _get_available_staff_users()
    return render_template(
        "contact_form.html",
        contact=None,
        contact_types=CONTACT_TYPES,
        staff_users=staff_users,
        form_action=url_for("contacts.create_contact"),
        page_title="Add Contact",
        submit_label="Create Contact",
    )


@contacts_bp.route("/<int:contact_id>", methods=["GET"])
@login_required
def contact_detail(contact_id: int):
    contact = _get_contact_or_404(contact_id)
    name_ci = contact.name.lower()

    # Build list of names to match (contact name + linked user name if exists)
    names_to_match = [name_ci]
    if contact.user:
        user_name_ci = contact.user.name.lower()
        if user_name_ci != name_ci:
            names_to_match.append(user_name_ci)

    assigned_items = Item.query.filter(
        Item.assigned_to.isnot(None),
        func.lower(Item.assigned_to).in_(names_to_match),
    ).order_by(Item.label.asc()).all()

    active_checkouts = (
        ItemCheckout.query
        .filter(
            ItemCheckout.is_active.is_(True),
            func.lower(ItemCheckout.checked_out_to).in_(names_to_match),
        )
        .order_by(ItemCheckout.checked_out_at.desc())
        .all()
    )

    recent_history = (
        ItemCheckout.query
        .filter(
            ItemCheckout.is_active.is_(False),
            func.lower(ItemCheckout.checked_out_to).in_(names_to_match),
        )
        .order_by(ItemCheckout.checked_in_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "contact_detail.html",
        contact=contact,
        assigned_items=assigned_items,
        active_checkouts=active_checkouts,
        recent_history=recent_history,
    )


@contacts_bp.route("/<int:contact_id>/edit", methods=["GET", "POST"])
@login_required
def edit_contact(contact_id: int):
    contact = _get_contact_or_404(contact_id)

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        contact_type = (request.form.get("contact_type") or "").strip().lower()
        company = (request.form.get("company") or "").strip() or None
        email = (request.form.get("email") or "").strip() or None
        phone = (request.form.get("phone") or "").strip() or None
        notes = (request.form.get("notes") or "").strip() or None
        user_id_str = (request.form.get("user_id") or "").strip()

        errors: list[str] = []
        if not name:
            errors.append("Name is required.")
        if contact_type not in CONTACT_TYPES:
            errors.append("Select a valid contact type.")

        staff_user = None
        if contact_type == "staff" and user_id_str:
            try:
                user_id = int(user_id_str)
                staff_user = db.session.get(User, user_id)
            except ValueError:
                staff_user = None
            if staff_user is None:
                errors.append("Selected staff user could not be found.")
            elif staff_user.contact_profile is not None and staff_user.contact_profile.id != contact.id:
                errors.append("That user is already linked to another contact.")

        if errors:
            for message in errors:
                flash(message, "error")
            return redirect(url_for("contacts.edit_contact", contact_id=contact.id))

        contact.name = name
        contact.contact_type = contact_type
        contact.company = company
        contact.email = email
        contact.phone = phone
        contact.notes = notes
        contact.user = staff_user

        db.session.commit()
        flash("Contact updated.", "success")
        return redirect(url_for("contacts.contact_detail", contact_id=contact.id))

    staff_users = _get_available_staff_users(include_user_id=contact.user_id)
    return render_template(
        "contact_form.html",
        contact=contact,
        contact_types=CONTACT_TYPES,
        staff_users=staff_users,
        form_action=url_for("contacts.edit_contact", contact_id=contact.id),
        page_title="Edit Contact",
        submit_label="Save Changes",
    )


@contacts_bp.route("/<int:contact_id>/delete", methods=["POST"])
@login_required
def delete_contact(contact_id: int):
    contact = _get_contact_or_404(contact_id)
    db.session.delete(contact)
    db.session.commit()
    flash("Contact removed.", "success")
    return redirect(url_for("contacts.list_contacts"))


@contacts_bp.route("/search", methods=["GET"])
@login_required
def search_contacts():
    """Search contacts for autocomplete - returns JSON"""
    from flask import jsonify

    query = (request.args.get("q") or "").strip()
    if not query or len(query) < 2:
        return jsonify([])

    like = f"%{query}%"
    contacts = Contact.query.filter(
        or_(
            Contact.name.ilike(like),
            Contact.email.ilike(like),
            Contact.company.ilike(like),
        )
    ).order_by(Contact.name.asc()).limit(10).all()

    return jsonify([{
        "id": c.id,
        "name": c.name,
        "company": c.company,
        "email": c.email,
        "contact_type": c.contact_type,
        "display": f"{c.name}" + (f" ({c.company})" if c.company else "")
    } for c in contacts])

