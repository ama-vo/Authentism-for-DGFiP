from datetime import datetime

from flask import Blueprint, current_app, g, jsonify, request

from extensions import db, limiter
from models import PendingMfa, Session, User
from security import (
    check_code,
    check_password,
    client_ip,
    hash_code,
    is_fiscal_id_valid,
    log_event,
    require_session,
)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def utcnow():
    return datetime.utcnow()


def _mint_code() -> str:
    import secrets

    return f"{secrets.randbelow(900000) + 100000}"


@bp.post("/login")
@limiter.limit(lambda: current_app.config["LOGIN_RATE_LIMIT"])
def login():
    data = request.get_json(silent=True) or {}
    fiscal_id = str(data.get("fiscal_id", "")).strip()
    password = str(data.get("password", ""))

    if not is_fiscal_id_valid(fiscal_id):
        log_event(fiscal_id or "inconnu", "Tentative de connexion refusée (identifiant invalide)", "/api/auth/login")
        return jsonify({"error": "Le numéro fiscal doit comporter exactement 13 chiffres."}), 400

    user = User.query.filter_by(fiscal_id=fiscal_id).first()

    # Message générique volontaire (identifiant inconnu ou mot de passe
    # erroné) pour ne pas permettre l'énumération de comptes existants.
    if not user or not check_password(user.password_hash, password):
        log_event(fiscal_id, "Tentative de connexion refusée (identifiants invalides)", "/api/auth/login")
        return jsonify({"error": "Identifiant ou mot de passe incorrect."}), 401

    code = _mint_code()
    pending = PendingMfa(
        pending_token=PendingMfa.new_pending_token(),
        user_id=user.id,
        code_hash=hash_code(code),
        expires_at=utcnow() + current_app.config["MFA_CODE_LIFETIME"],
    )
    db.session.add(pending)
    db.session.commit()

    _send_mfa_email(user, code)
    log_event(fiscal_id, "Identifiant et mot de passe validés — code MFA envoyé", "/api/auth/login")

    response = {
        "pending_token": pending.pending_token,
        "expires_in_seconds": int(current_app.config["MFA_CODE_LIFETIME"].total_seconds()),
    }
    # Ne jamais activer en production : uniquement pour tester le
    # parcours sans expéditeur d'e-mail réel.
    if current_app.config["DEBUG_EXPOSE_MFA_CODE"]:
        response["debug_code"] = code

    return jsonify(response), 200


@bp.post("/mfa/verify")
@limiter.limit(lambda: current_app.config["MFA_RATE_LIMIT"])
def mfa_verify():
    data = request.get_json(silent=True) or {}
    pending_token = str(data.get("pending_token", ""))
    code = str(data.get("code", "")).strip()

    pending = PendingMfa.query.filter_by(pending_token=pending_token).first()
    if not pending or not pending.is_valid():
        log_event("inconnu", "Échec MFA (jeton d'attente invalide ou expiré)", "/api/auth/mfa/verify")
        return jsonify({"error": "Session d'authentification expirée. Reconnectez-vous."}), 400

    user = User.query.get(pending.user_id)

    if pending.attempts >= current_app.config["MFA_MAX_ATTEMPTS"]:
        db.session.delete(pending)
        db.session.commit()
        log_event(user.fiscal_id, "Compte temporairement bloqué (échecs MFA répétés)", "/api/auth/mfa/verify")
        return jsonify({"error": "Nombre maximal de tentatives atteint."}), 429

    if not check_code(pending.code_hash, code):
        pending.attempts += 1
        db.session.commit()
        remaining = current_app.config["MFA_MAX_ATTEMPTS"] - pending.attempts
        log_event(user.fiscal_id, "Échec de vérification MFA", "/api/auth/mfa/verify")
        return jsonify({"error": "Code incorrect.", "attempts_remaining": max(0, remaining)}), 401

    session = Session(
        token=Session.new_token(),
        user_id=user.id,
        scope="normal",
        expires_at=utcnow() + current_app.config["NORMAL_SESSION_LIFETIME"],
    )
    db.session.add(session)
    db.session.delete(pending)
    db.session.commit()

    log_event(user.fiscal_id, "Double authentification réussie — session ouverte", "/api/auth/mfa/verify")

    return jsonify({
        "token": session.token,
        "role": user.role,
        "fiscal_id": user.fiscal_id,
        "name": user.name,
    }), 200


@bp.post("/mfa/resend")
@limiter.limit(lambda: current_app.config["MFA_RATE_LIMIT"])
def mfa_resend():
    data = request.get_json(silent=True) or {}
    pending_token = str(data.get("pending_token", ""))

    pending = PendingMfa.query.filter_by(pending_token=pending_token).first()
    if not pending or not pending.is_valid():
        return jsonify({"error": "Session d'authentification expirée. Reconnectez-vous."}), 400

    user = User.query.get(pending.user_id)
    code = _mint_code()
    pending.code_hash = hash_code(code)
    pending.attempts = 0
    pending.expires_at = utcnow() + current_app.config["MFA_CODE_LIFETIME"]
    db.session.commit()

    _send_mfa_email(user, code)
    log_event(user.fiscal_id, "Renvoi du code MFA", "/api/auth/mfa/resend")

    response = {"expires_in_seconds": int(current_app.config["MFA_CODE_LIFETIME"].total_seconds())}
    if current_app.config["DEBUG_EXPOSE_MFA_CODE"]:
        response["debug_code"] = code
    return jsonify(response), 200


@bp.post("/logout")
@require_session(scope="normal")
def logout():
    log_event(g.user.fiscal_id, "Déconnexion", "/api/auth/logout")
    db.session.delete(g.session)
    db.session.commit()
    return jsonify({"ok": True}), 200


@bp.get("/me")
@require_session(scope="normal")
def me():
    return jsonify(g.user.to_public_dict()), 200


def _send_mfa_email(user: User, code: str) -> None:
    """Emplacement d'intégration du fournisseur d'e-mail transactionnel
    réel (ex. un service d'envoi géré côté infrastructure). Ici, on se
    contente de journaliser côté serveur pour la démonstration —
    le code ne doit jamais transiter ailleurs que par ce canal chiffré."""
    current_app.logger.info(
        "[MFA] Envoi du code %s à %s (%s)", code, user.email, user.fiscal_id
    )
