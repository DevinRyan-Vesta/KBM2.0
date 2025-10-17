# utilities/database.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from typing import Any, Dict, Optional, Union

db = SQLAlchemy()

class Item(db.Model):
    __tablename__ = "items"
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)        # "Lockbox" | "Key" | "Sign"
    label = db.Column(db.String(120), nullable=False)      # e.g., "LB-A12"
    location = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="available")  # available|checked_out|assigned

    # NEW lockbox-centric fields
    address = db.Column(db.String(255), nullable=True)      # search helper
    code_current = db.Column(db.String(20), nullable=True)
    code_previous = db.Column(db.String(20), nullable=True)

    last_action = db.Column(db.String(50), nullable=True)   # "added" | "checked_out" | "checked_in" | "assigned"
    last_action_at = db.Column(db.DateTime, nullable=True)
    last_action_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    last_action_by = db.relationship("User", foreign_keys=[last_action_by_id])

    # optional assignment target (agent, property, etc.)
    assigned_to = db.Column(db.String(120), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def record_action(self, action: str, user: "User"):
        self.last_action = action
        self.last_action_at = datetime.utcnow()
        self.last_action_by = user

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "location": self.location,
            "status": self.status,
            "address": self.address,
            "code_current": self.code_current,
            "code_previous": self.code_previous,
            "last_action": self.last_action,
            "last_action_at": self.last_action_at.isoformat() if self.last_action_at else None,
            "last_action_by": self.last_action_by.name if self.last_action_by else None,
            "assigned_to": self.assigned_to,
        }

class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(1200), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default="user")  # e.g., "admin", "user"
    pin_hash = db.Column(db.String(255), nullable=False)


    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())
    def set_pin(self, raw_pin: str):
        self.pin_hash = generate_password_hash(raw_pin)

    def check_pin(self, raw_pin: str) -> bool:
        return check_password_hash(self.pin_hash, raw_pin)

class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    user = db.relationship("User", lazy="joined")
    action = db.Column(db.String(120), nullable=False)
    target_type = db.Column(db.String(120), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    summary = db.Column(db.String(255), nullable=True)
    meta = db.Column(db.JSON, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "user_id": self.user_id,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "summary": self.summary,
            "meta": self.meta,
        }

def log_activity(
    action: str,
    *,
    user: Optional[Union[User, int]] = None,
    target: Optional[Any] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    summary: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    commit: bool = False,
) -> ActivityLog:
    """Persist a structured audit trail entry."""
    entry = ActivityLog(
        action=action,
        user_id=_extract_id(user),
        target_type=target_type or _extract_target_type(target),
        target_id=target_id or _extract_id(target),
        summary=summary,
        meta=meta or None,
    )
    db.session.add(entry)

    if commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

    return entry

def _extract_id(candidate: Optional[Union[User, Item, ActivityLog, int]]) -> Optional[int]:
    if candidate is None:
        return None
    if isinstance(candidate, int):
        return candidate
    return getattr(candidate, "id", None)

def _extract_target_type(target: Optional[Any]) -> Optional[str]:
    if target is None:
        return None
    return target.__class__.__name__
