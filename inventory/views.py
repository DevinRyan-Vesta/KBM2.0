# inventory/views.py
from flask import Blueprint, render_template, request, redirect, url_for
from utilities.database import db, Item  # Item is our table model

inventory_bp = Blueprint("inventory", __name__, template_folder="../templates")

@inventory_bp.get("/lockboxes")
def list_lockboxes():
    rows = Item.query.filter_by(type="Lockbox").order_by(Item.id.desc()).all()
    return render_template("lockboxes_list.html", lockboxes=rows)

@inventory_bp.post("/lockboxes")
def add_lockbox():
    label = request.form.get("label", "").strip()
    location = request.form.get("location", "").strip()
    if label:
        row = Item(type="Lockbox", label=label, location=location)
        db.session.add(row)
        db.session.commit()
    return redirect(url_for("inventory.list_lockboxes"))