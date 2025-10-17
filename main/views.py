from flask import Blueprint, render_template, url_for, redirect
from flask_login import login_required, current_user
from utilities.database import db, User, Item


main_bp = Blueprint(
    "main",
    __name__,
    template_folder="../templates",
    static_folder="../static"
)


@main_bp.route("/", methods=["GET"])
@login_required
def home():
    #Grab the latest 5 of each type (Safe even if some types don't exist)
    lockboxes = Item.query.filter_by(type="Lockbox").order_by(Item.id.desc()).limit(5).all()
    keys = Item.query.filter_by(type="Key").order_by(Item.id.desc()).limit(5).all()
    signs = Item.query.filter_by(type="Sign").order_by(Item.id.desc()).limit(5).all()

    return render_template(
        "home.html", 
        lockboxes=lockboxes, 
        keys=keys, 
        signs=signs
        
    )