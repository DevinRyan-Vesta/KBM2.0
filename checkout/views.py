# checkout/views.py
from flask import Blueprint, render_template
from flask_login import login_required

checkout_bp = Blueprint(
    "checkout",
    __name__,
    template_folder="../templates",
    static_folder="../static"
)


@checkout_bp.get("/")
@login_required
def start():
    return render_template("checkout_start.html")


@checkout_bp.get("/ping")
def checkout_ping():
    return "Checkout blueprint is alive", 200
