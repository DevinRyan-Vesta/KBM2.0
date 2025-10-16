# utilities/database.py
from flask_sqlalchemy import SQLAlchemy  # ✅ correct package/module
db = SQLAlchemy()

# Minimal Item model so Lockboxes can work now
class Item(db.Model):
    __tablename__ = "items"

    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)     # e.g., "Lockbox"
    label = db.Column(db.String(120), nullable=False)   # e.g., "LB-A12"
    location = db.Column(db.String(120), nullable=True) # e.g., "Front Desk"
    status = db.Column(db.String(20), nullable=False)    # e.g., "Available", "Checked Out"

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "location": self.location,
            "status": self.status,
        }
