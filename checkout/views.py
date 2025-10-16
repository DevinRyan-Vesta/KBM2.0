# checkout/views.py
from flask import Blueprint

checkout_bp = Blueprint(
    "checkout",
    __name__,
    template_folder="../templates",
    static_folder="../static"
)

@checkout_bp.get("/checkout/ping")
def checkout_ping():
    return "Checkout blueprint is alive", 200
