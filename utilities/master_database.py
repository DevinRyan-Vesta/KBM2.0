"""
Master database models for multi-tenant architecture.
This database stores account/tenant information and user authentication.
Each tenant gets their own separate SQLite database for operational data.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, UTC
import secrets

# Master database instance (separate from tenant databases)
master_db = SQLAlchemy()


def utc_now() -> datetime:
    """Return a naive UTC datetime without relying on deprecated utcnow()."""
    return datetime.now(UTC).replace(tzinfo=None)


class Account(master_db.Model):
    """
    Represents a company/tenant account.
    Each account gets its own database file.
    """
    __tablename__ = "accounts"

    id = master_db.Column(master_db.Integer, primary_key=True)
    subdomain = master_db.Column(master_db.String(63), unique=True, nullable=False, index=True)
    company_name = master_db.Column(master_db.String(255), nullable=False)
    status = master_db.Column(master_db.String(20), nullable=False, default="active")  # active|suspended|deleted
    database_path = master_db.Column(master_db.String(512), nullable=False)

    # Limits and quotas (optional - for future use)
    max_users = master_db.Column(master_db.Integer, nullable=True, default=25)
    max_items = master_db.Column(master_db.Integer, nullable=True, default=1000)

    created_at = master_db.Column(master_db.DateTime, nullable=False, default=utc_now)
    updated_at = master_db.Column(master_db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    # Relationships
    users = master_db.relationship("MasterUser", back_populates="account", cascade="all, delete-orphan")
    invitations = master_db.relationship("Invitation", back_populates="account", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "subdomain": self.subdomain,
            "company_name": self.company_name,
            "status": self.status,
            "max_users": self.max_users,
            "max_items": self.max_items,
            "created_at": self.created_at.isoformat(),
            "user_count": len(self.users),
        }

    @staticmethod
    def validate_subdomain(subdomain: str) -> tuple[bool, str]:
        """
        Validate subdomain format and availability.
        Returns (is_valid, error_message)
        """
        if not subdomain:
            return False, "Subdomain is required"

        subdomain = subdomain.lower().strip()

        # Check length
        if len(subdomain) < 3:
            return False, "Subdomain must be at least 3 characters"
        if len(subdomain) > 63:
            return False, "Subdomain must be 63 characters or less"

        # Check format (alphanumeric and hyphens, must start/end with alphanumeric)
        import re
        if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', subdomain):
            return False, "Subdomain must contain only lowercase letters, numbers, and hyphens (cannot start or end with hyphen)"

        # Check reserved subdomains
        reserved = ['www', 'admin', 'api', 'app', 'mail', 'ftp', 'localhost', 'staging', 'dev', 'test']
        if subdomain in reserved:
            return False, f"'{subdomain}' is a reserved subdomain"

        # Check availability
        existing = Account.query.filter_by(subdomain=subdomain).first()
        if existing:
            return False, "This subdomain is already taken"

        return True, ""


class MasterUser(master_db.Model, UserMixin):
    """
    User authentication table in master database.
    Contains all users across all tenants.
    """
    __tablename__ = "master_users"

    id = master_db.Column(master_db.Integer, primary_key=True)
    account_id = master_db.Column(master_db.Integer, master_db.ForeignKey("accounts.id"), nullable=True, index=True)

    name = master_db.Column(master_db.String(200), nullable=False)
    email = master_db.Column(master_db.String(255), nullable=False, index=True)
    pin_hash = master_db.Column(master_db.String(255), nullable=False)

    # Role: 'app_admin' (super admin), 'admin' (tenant admin), 'user' (regular tenant user)
    role = master_db.Column(master_db.String(20), nullable=False, default="user")

    is_active = master_db.Column(master_db.Boolean, default=True)
    created_at = master_db.Column(master_db.DateTime, nullable=False, default=utc_now)
    updated_at = master_db.Column(master_db.DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    last_login_at = master_db.Column(master_db.DateTime, nullable=True)

    # Relationships
    account = master_db.relationship("Account", back_populates="users")

    def set_pin(self, raw_pin: str):
        """Hash and set the user's PIN."""
        self.pin_hash = generate_password_hash(raw_pin)

    def check_pin(self, raw_pin: str) -> bool:
        """Verify the user's PIN."""
        return check_password_hash(self.pin_hash, raw_pin)

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }

    # Make email unique per account (not globally)
    __table_args__ = (
        master_db.UniqueConstraint('account_id', 'email', name='uq_account_email'),
    )


class Invitation(master_db.Model):
    """
    Invitation system for adding users to accounts.
    Only admins and app admins can create invitations.
    """
    __tablename__ = "invitations"

    id = master_db.Column(master_db.Integer, primary_key=True)
    account_id = master_db.Column(master_db.Integer, master_db.ForeignKey("accounts.id"), nullable=False, index=True)

    email = master_db.Column(master_db.String(255), nullable=False, index=True)
    name = master_db.Column(master_db.String(200), nullable=False)
    role = master_db.Column(master_db.String(20), nullable=False, default="user")  # admin or user

    token = master_db.Column(master_db.String(64), unique=True, nullable=False, index=True)

    # Who created the invitation
    invited_by_id = master_db.Column(master_db.Integer, master_db.ForeignKey("master_users.id"), nullable=False)
    invited_by = master_db.relationship("MasterUser", foreign_keys=[invited_by_id])

    # Status tracking
    status = master_db.Column(master_db.String(20), nullable=False, default="pending")  # pending|accepted|expired|revoked

    created_at = master_db.Column(master_db.DateTime, nullable=False, default=utc_now)
    expires_at = master_db.Column(master_db.DateTime, nullable=False)
    accepted_at = master_db.Column(master_db.DateTime, nullable=True)

    # Relationships
    account = master_db.relationship("Account", back_populates="invitations")

    @staticmethod
    def generate_token() -> str:
        """Generate a secure random token for invitation."""
        return secrets.token_urlsafe(48)

    def is_valid(self) -> bool:
        """Check if invitation is still valid."""
        if self.status != "pending":
            return False
        if self.expires_at < utc_now():
            self.status = "expired"
            return False
        return True

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "invited_by": self.invited_by.name if self.invited_by else None,
        }
