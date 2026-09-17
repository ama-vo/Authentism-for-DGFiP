import re
from datetime import datetime, timezone
from functools import wraps

from flask import current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import AuditLog, Session

FISCAL_ID_RE = re.compile(r"^\d{13}$")

# Endpoints considérés comme sensibles -> priorité "high" dans le journal
# (§3.2 : accès admin, réinitialisation mdp, création/suppression de compte)
HIGH_PRIORITY_ACTIONS = (
    "admin",
    "mfa",
    "reset-password",
    "accounts/create",
    "accounts/delete",
    "access-denied",
)


def validate_password(password: str) -> dict:
    """Retourne le détail des règles respectées (§2.1)."""
    return {
        "length": len(password) >= current_app.config["PASSWORD_MIN_LENGTH"],
        "uppercase": bool(re.search(r"[A-Z]", password)),
        "lowercase": bool(re.search(r"[a-z]", password)),
        "digit": bool(re.search(r"[0-9]", password)),
        "special": bool(re.search(r"[^A-Za-z0-9]", password)),
    }


def is_password_valid(password: str) -> bool:
    return all(validate_password(password).values())


def is_fiscal_id_valid(fiscal_id: str) -> bool:
    return bool(fiscal_id) and bool(FISCAL_ID_RE.match(fiscal_id))


def hash_password(password: str) -> str:
    return generate_password_hash(password, method="pbkdf2:sha256:600000")


def check_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)


def hash_code(code: str) -> str:
    # Même mécanisme de hachage que les mots de passe : le code MFA
    # ne doit jamais être récupérable en clair depuis la base.
    return generate_password_hash(code, method="pbkdf2:sha256:150000")


def check_code(code_hash: str, code: str) -> bool:
    return check_password_hash(code_hash, code)


def client_ip() -> str:
    # Derrière un load balancer/reverse proxy, ne faire confiance à
    # X-Forwarded-For que si celui-ci est configuré pour l'écraser
    # correctement (sinon un client peut usurper l'en-tête).
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "inconnu"


def log_event(account: str, action: str, endpoint: str, priority: str | None = None) -> None:
    if priority is None:
        priority = "high" if any(k in endpoint for k in HIGH_PRIORITY_ACTIONS) else "normal"
    entry = AuditLog(
        account=account or "inconnu",
        action=action,
        endpoint=endpoint,
        ip_address=client_ip(),
        priority=priority,
    )
    db.session.add(entry)
    db.session.commit()


def require_session(scope: str = "normal", roles: tuple | None = None):
    """Décorateur imposant un jeton de session valide, d'une portée
    donnée (normale ou admin) et, optionnellement, un ou plusieurs rôles.
    Toute tentative refusée est journalisée avec une priorité élevée."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            token = auth_header[7:] if auth_header.startswith("Bearer ") else None

            if not token:
                log_event("inconnu", "Accès refusé (jeton manquant)", request.path, "high")
                return jsonify({"error": "Authentification requise."}), 401

            session = Session.query.filter_by(token=token).first()
            if not session or not session.is_valid():
                log_event("inconnu", "Accès refusé (jeton invalide ou expiré)", request.path, "high")
                return jsonify({"error": "Session invalide ou expirée."}), 401

            if session.scope != scope:
                log_event(session.user.fiscal_id, "Accès refusé (portée de jeton insuffisante)", request.path, "high")
                return jsonify({"error": "Cette action nécessite un jeton d'une autre portée."}), 403

            if roles and session.user.role not in roles:
                log_event(session.user.fiscal_id, "Accès refusé (rôle non autorisé)", request.path, "high")
                return jsonify({"error": "Votre rôle ne permet pas cette action."}), 403

            g.session = session
            g.user = session.user
            return fn(*args, **kwargs)

        return wrapper

    return decorator
