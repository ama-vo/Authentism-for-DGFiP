import secrets
import uuid
from datetime import datetime

from extensions import db

ROLES = ("external", "agent", "admin")


def utcnow():
    # Naive UTC volontairement : SQLite ne conserve pas le fuseau horaire,
    # on reste donc cohérent en UTC naïf partout dans l'application.
    return datetime.utcnow()


class User(db.Model):
    """Compte DGFiP. L'identifiant métier est le numéro fiscal (13 chiffres)."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    fiscal_id = db.Column(db.String(13), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="external")
    created_at = db.Column(db.DateTime, default=utcnow)

    sessions = db.relationship("Session", backref="user", cascade="all, delete-orphan")

    def to_public_dict(self):
        return {
            "id": self.id,
            "fiscal_id": self.fiscal_id,
            "name": self.name,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
        }


class Session(db.Model):
    """Jeton de session stocké côté serveur (§2.2 / §2.3 du cahier des charges).
    Le client ne reçoit que le jeton opaque — jamais de données déchiffrables
    côté client type JWT auto-porteur pour les informations sensibles."""

    __tablename__ = "sessions"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    scope = db.Column(db.String(20), nullable=False, default="normal")  # "normal" ou "admin"
    created_at = db.Column(db.DateTime, default=utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    @staticmethod
    def new_token():
        return secrets.token_urlsafe(32)

    def is_valid(self):
        return utcnow() < self.expires_at


class PendingMfa(db.Model):
    """État transitoire entre l'étape mot de passe et l'étape MFA.
    Le code n'est jamais stocké en clair."""

    __tablename__ = "pending_mfa"

    id = db.Column(db.Integer, primary_key=True)
    pending_token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    code_hash = db.Column(db.String(255), nullable=False)
    attempts = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    @staticmethod
    def new_pending_token():
        return secrets.token_urlsafe(24)

    def is_valid(self):
        return utcnow() < self.expires_at


class AuditLog(db.Model):
    """Journal de traçabilité (§3.2) : horodatage, compte, action, endpoint, IP."""

    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=utcnow, index=True)
    account = db.Column(db.String(64), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    endpoint = db.Column(db.String(255), nullable=False)
    ip_address = db.Column(db.String(64), nullable=False)
    priority = db.Column(db.String(10), nullable=False, default="normal")  # "normal" ou "high"

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "account": self.account,
            "action": self.action,
            "endpoint": self.endpoint,
            "ip_address": self.ip_address,
            "priority": self.priority,
        }


def gen_uuid():
    return str(uuid.uuid4())
