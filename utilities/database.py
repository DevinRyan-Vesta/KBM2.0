# utilities/database.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, UTC
from typing import Any, Dict, Optional, Union, List

db = SQLAlchemy()


def utc_now() -> datetime:
    """Return a naive UTC datetime without relying on deprecated utcnow()."""
    return datetime.now(UTC).replace(tzinfo=None)

class Item(db.Model):
    __tablename__ = "items"
    id = db.Column(db.Integer, primary_key=True)
    custom_id = db.Column(db.String(20), unique=True, nullable=True, index=True)  # e.g., "LBA001", "KA042", "SA123"
    type = db.Column(db.String(50), nullable=False)        # "Lockbox" | "Key" | "Sign"
    label = db.Column(db.String(120), nullable=False)      # e.g., "LB-A12"
    location = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="available")  # available|checked_out|assigned

    # Lockbox-specific fields
    address = db.Column(db.String(255), nullable=True)      # search helper
    code_current = db.Column(db.String(20), nullable=True)
    code_previous = db.Column(db.String(20), nullable=True)
    supra_id = db.Column(db.String(50), nullable=True)  # Supra lockbox ID

    # Key-specific fields
    key_hook_number = db.Column(db.String(20), nullable=True)  # Key Hook # in key box
    keycode = db.Column(db.String(20), nullable=True)  # Key code (5-digit cut code)
    total_copies = db.Column(db.Integer, nullable=True, default=0)  # Total key copies
    copies_checked_out = db.Column(db.Integer, nullable=True, default=0)  # Currently checked out
    checkout_purpose = db.Column(db.String(255), nullable=True)  # Purpose of checkout
    expected_return_date = db.Column(db.DateTime, nullable=True)  # Expected return date
    assignment_type = db.Column(db.String(50), nullable=True)  # tenant|contractor|property

    # Sign-specific fields
    sign_subtype = db.Column(db.String(20), nullable=True)  # "Piece" | "Assembled Unit"
    piece_type = db.Column(db.String(20), nullable=True)  # "Frame" | "Sign" | "Name Rider" | "Status Rider" | "Bonus Rider"
    parent_sign_id = db.Column(db.Integer, nullable=True)  # Parent assembled unit (FK to items.id)
    rider_text = db.Column(db.String(255), nullable=True)  # Text for Name/Status/Bonus riders
    material = db.Column(db.String(100), nullable=True)  # Material of sign/piece
    condition = db.Column(db.String(50), nullable=True)  # Condition (Good, Fair, Poor, etc.)

    last_action = db.Column(db.String(50), nullable=True)   # "added" | "checked_out" | "checked_in" | "assigned"
    last_action_at = db.Column(db.DateTime, nullable=True)
    # In multi-tenant setup, user IDs reference MasterUser in master DB, not tenant users table
    last_action_by_id = db.Column(db.Integer, nullable=True)

    # optional assignment target (agent, property, etc.)
    assigned_to = db.Column(db.String(120), nullable=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=True)
    property_unit_id = db.Column(db.Integer, db.ForeignKey("property_units.id"), nullable=True)

    # Master key relationship - links a key to another key as its master
    master_key_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    property = db.relationship("Property", back_populates="items")
    property_unit = db.relationship("PropertyUnit", back_populates="items")

    # Master key relationships
    master_key = db.relationship("Item", remote_side=[id], foreign_keys=[master_key_id], backref="child_keys")

    def record_action(self, action: str, user: "User"):
        self.last_action = action
        self.last_action_at = utc_now()
        self.last_action_by = user

    def to_dict(self):
        return {
            "id": self.id,
            "custom_id": self.custom_id,
            "type": self.type,
            "label": self.label,
            "location": self.location,
            "status": self.status,
            "address": self.address,
            "code_current": self.code_current,
            "code_previous": self.code_previous,
            "key_hook_number": self.key_hook_number,
            "keycode": self.keycode,
            "total_copies": self.total_copies,
            "copies_checked_out": self.copies_checked_out,
            "checkout_purpose": self.checkout_purpose,
            "expected_return_date": self.expected_return_date.isoformat() if self.expected_return_date else None,
            "assignment_type": self.assignment_type,
            "sign_subtype": self.sign_subtype,
            "piece_type": self.piece_type,
            "parent_sign_id": self.parent_sign_id,
            "rider_text": self.rider_text,
            "material": self.material,
            "condition": self.condition,
            "last_action": self.last_action,
            "last_action_at": self.last_action_at.isoformat() if self.last_action_at else None,
            "last_action_by_id": self.last_action_by_id,
            "assigned_to": self.assigned_to,
            "property_id": self.property_id,
            "property_name": self.property.name if self.property else None,
            "property_unit_id": self.property_unit_id,
            "property_unit_label": self.property_unit.label if self.property_unit else None,
            "master_key_id": self.master_key_id,
            "master_key_label": self.master_key.label if self.master_key else None,
            "master_key_custom_id": self.master_key.custom_id if self.master_key else None,
        }

    @staticmethod
    def generate_custom_id(item_type: str, sign_subtype: Optional[str] = None) -> str:
        """Generate next available custom ID for given item type"""
        from utilities.tenant_helpers import get_tenant_session

        # Define prefixes and ranges
        if item_type == "Lockbox":
            prefix = "LB"
            letter_range = range(ord('A'), ord('Z') + 1)  # A-Z
        elif item_type == "Key":
            prefix = "K"
            letter_range = range(ord('A'), ord('Z') + 1)  # A-Z
        elif item_type == "Sign":
            # Assembled signs get ASA prefix, individual pieces get S prefix
            if sign_subtype == "Assembled Unit":
                prefix = "AS"
            else:
                prefix = "S"
            letter_range = range(ord('A'), ord('Z') + 1)  # A-Z
        else:
            raise ValueError(f"Unknown item type: {item_type}")

        # Find the highest existing ID for this type and prefix
        existing_ids = get_tenant_session().query(Item.custom_id).filter(
            Item.type == item_type,
            Item.custom_id.isnot(None),
            Item.custom_id.like(f"{prefix}%")
        ).all()

        existing_ids = [row[0] for row in existing_ids if row[0]]

        # If no existing IDs, start with first one
        if not existing_ids:
            return f"{prefix}A001"

        # Parse existing IDs to find the highest
        max_letter = 'A'
        max_number = 0

        for custom_id in existing_ids:
            if custom_id and custom_id.startswith(prefix):
                # Extract letter and number (e.g., "LBA001" -> "A", 1)
                remainder = custom_id[len(prefix):]
                if len(remainder) >= 4:
                    letter = remainder[0]
                    try:
                        number = int(remainder[1:])
                        if letter > max_letter or (letter == max_letter and number > max_number):
                            max_letter = letter
                            max_number = number
                    except ValueError:
                        continue

        # Increment to next ID
        max_number += 1

        # Check if we need to move to next letter
        if max_number > 999:
            max_number = 1
            if max_letter == 'Z':
                raise ValueError(f"Ran out of IDs for {item_type} (reached ZZ999)")
            max_letter = chr(ord(max_letter) + 1)

        return f"{prefix}{max_letter}{max_number:03d}"


class Property(db.Model):
    __tablename__ = "properties"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False, default="single_family")
    address_line1 = db.Column(db.String(255), nullable=False)
    address_line2 = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(120), nullable=True)
    state = db.Column(db.String(80), nullable=True)
    postal_code = db.Column(db.String(20), nullable=True)
    country = db.Column(db.String(80), nullable=True, default="USA")
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    items = db.relationship("Item", back_populates="property")
    units = db.relationship("PropertyUnit", back_populates="property", cascade="all, delete-orphan")
    smart_locks = db.relationship("SmartLock", back_populates="property", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "address_line1": self.address_line1,
            "address_line2": self.address_line2,
            "city": self.city,
            "state": self.state,
            "postal_code": self.postal_code,
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "notes": self.notes,
        }


class PropertyUnit(db.Model):
    __tablename__ = "property_units"

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False, index=True)
    label = db.Column(db.String(120), nullable=False)
    floor = db.Column(db.String(50), nullable=True)
    bedrooms = db.Column(db.Integer, nullable=True)
    bathrooms = db.Column(db.Numeric(4, 1), nullable=True)
    square_feet = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    property = db.relationship("Property", back_populates="units")
    items = db.relationship("Item", back_populates="property_unit")
    smart_locks = db.relationship("SmartLock", back_populates="property_unit")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "property_id": self.property_id,
            "label": self.label,
            "floor": self.floor,
            "bedrooms": self.bedrooms,
            "bathrooms": float(self.bathrooms) if self.bathrooms is not None else None,
            "square_feet": self.square_feet,
            "notes": self.notes,
        }


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(1200), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default="user")  # e.g., "admin", "user"
    pin_hash = db.Column(db.String(255), nullable=False)

    # Relationship to Contact
    contact_profile = db.relationship("Contact", back_populates="user", uselist=False)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.now())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.now(), onupdate=db.func.now())
    def set_pin(self, raw_pin: str):
        self.pin_hash = generate_password_hash(raw_pin)

    def check_pin(self, raw_pin: str) -> bool:
        return check_password_hash(self.pin_hash, raw_pin)


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    contact_type = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    company = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), nullable=True, index=True)
    phone = db.Column(db.String(50), nullable=True)
    # In multi-tenant setup, user IDs reference MasterUser in master DB
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, unique=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    # Relationship to User
    user = db.relationship("User", back_populates="contact_profile")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "contact_type": self.contact_type,
            "name": self.name,
            "company": self.company,
            "email": self.email,
            "phone": self.phone,
            "user_id": self.user_id,
            "notes": self.notes,
        }


class ItemCheckout(db.Model):
    """Tracks individual checkouts/assignments of items or copies"""
    __tablename__ = "item_checkouts"

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    item = db.relationship("Item", backref="checkouts")

    # Who has it
    checked_out_to = db.Column(db.String(255), nullable=False)  # Name or company
    # In multi-tenant setup, user IDs reference MasterUser in master DB
    checked_out_by_id = db.Column(db.Integer, nullable=True)

    # Details
    quantity = db.Column(db.Integer, nullable=False, default=1)  # Number of copies (for keys)
    purpose = db.Column(db.String(255), nullable=True)
    assignment_type = db.Column(db.String(50), nullable=True)  # tenant|contractor|property
    expected_return_date = db.Column(db.DateTime, nullable=True)
    address = db.Column(db.String(255), nullable=True)  # Where it's being used

    # Timestamps
    checked_out_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    checked_in_at = db.Column(db.DateTime, nullable=True)  # NULL if still checked out
    # In multi-tenant setup, user IDs reference MasterUser in master DB
    checked_in_by_id = db.Column(db.Integer, nullable=True)

    # Status
    is_active = db.Column(db.Boolean, nullable=False, default=True)  # False if returned

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "item_id": self.item_id,
            "checked_out_to": self.checked_out_to,
            "checked_out_by": self.checked_out_by.name if self.checked_out_by else None,
            "quantity": self.quantity,
            "purpose": self.purpose,
            "assignment_type": self.assignment_type,
            "expected_return_date": self.expected_return_date.isoformat() if self.expected_return_date else None,
            "address": self.address,
            "checked_out_at": self.checked_out_at.isoformat() if self.checked_out_at else None,
            "checked_in_at": self.checked_in_at.isoformat() if self.checked_in_at else None,
            "checked_in_by": self.checked_in_by.name if self.checked_in_by else None,
            "is_active": self.is_active,
        }


class SmartLock(db.Model):
    __tablename__ = "smart_locks"

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(255), nullable=False)
    provider = db.Column(db.String(120), nullable=True)
    code = db.Column(db.String(120), nullable=False)
    backup_code = db.Column(db.String(120), nullable=True)
    instructions = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=True, index=True)
    property_unit_id = db.Column(db.Integer, db.ForeignKey("property_units.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    property = db.relationship("Property", back_populates="smart_locks")
    property_unit = db.relationship("PropertyUnit", back_populates="smart_locks")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "provider": self.provider,
            "code": self.code,
            "backup_code": self.backup_code,
            "instructions": self.instructions,
            "notes": self.notes,
            "property_id": self.property_id,
            "property_unit_id": self.property_unit_id,
        }


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    # In multi-tenant setup, user IDs reference MasterUser in master DB
    user_id = db.Column(db.Integer, nullable=True, index=True)
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


class Audit(db.Model):
    """Represents a key audit session"""
    __tablename__ = "audits"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    audit_date = db.Column(db.DateTime, nullable=False, default=utc_now)
    created_by_user_id = db.Column(db.Integer, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending|in_progress|completed
    notes = db.Column(db.Text, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    items = db.relationship("AuditItem", back_populates="audit", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "audit_date": self.audit_date.isoformat(),
            "created_by_user_id": self.created_by_user_id,
            "status": self.status,
            "notes": self.notes,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class AuditItem(db.Model):
    """Represents an individual item in an audit"""
    __tablename__ = "audit_items"

    id = db.Column(db.Integer, primary_key=True)
    audit_id = db.Column(db.Integer, db.ForeignKey("audits.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)

    # Expected values (snapshot at audit creation)
    expected_location = db.Column(db.String(120), nullable=True)  # keyhook number
    expected_quantity = db.Column(db.Integer, nullable=True)  # total_copies

    # Actual values (filled during audit)
    actual_location = db.Column(db.String(120), nullable=True)
    actual_quantity = db.Column(db.Integer, nullable=True)

    # Discrepancy tracking
    discrepancy_type = db.Column(db.String(50), nullable=True)  # none|missing|extra|wrong_location|quantity_mismatch
    notes = db.Column(db.Text, nullable=True)

    audited_at = db.Column(db.DateTime, nullable=True)  # When this specific item was audited

    # Relationships
    audit = db.relationship("Audit", back_populates="items")
    item = db.relationship("Item")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "audit_id": self.audit_id,
            "item_id": self.item_id,
            "expected_location": self.expected_location,
            "expected_quantity": self.expected_quantity,
            "actual_location": self.actual_location,
            "actual_quantity": self.actual_quantity,
            "discrepancy_type": self.discrepancy_type,
            "notes": self.notes,
            "audited_at": self.audited_at.isoformat() if self.audited_at else None,
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
    from utilities.tenant_helpers import tenant_add, tenant_commit, tenant_rollback

    entry = ActivityLog(
        action=action,
        user_id=_extract_id(user),
        target_type=target_type or _extract_target_type(target),
        target_id=target_id or _extract_id(target),
        summary=summary,
        meta=meta or None,
    )
    tenant_add(entry)

    if commit:
        try:
            tenant_commit()
        except Exception:
            tenant_rollback()
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
