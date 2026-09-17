from datetime import datetime

from flask import Blueprint, current_app, g, jsonify, request

from extensions import db
from models import AuditLog, Session, User
from security import (
    check_password,
    hash_password,
    is_fiscal_id_valid,
    is_password_valid,
    log_event,
    require_session,
    validate_password,
)

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def utcnow():
    return datetime.utcnow()


@bp.post("/token")
@require_session(scope="normal", roles=("admin",))
def elevate():
    """Délivre un second jeton de session, dédié aux fonctions
    d'administration, distinct du jeton de session normal (§2.4)."""
    data = request.get_json(silent=True) or {}
    password = str(data.get("password", ""))

    if not check_password(g.user.password_hash, password):
        log_event(g.user.fiscal_id, "Échec d'obtention du jeton d'administration", "/api/admin/token")
        return jsonify({"error": "Mot de passe incorrect."}), 401

    admin_session = Session(
        token=Session.new_token(),
        user_id=g.user.id,
        scope="admin",
        expires_at=utcnow() + current_app.config["ADMIN_SESSION_LIFETIME"],
    )
    db.session.add(admin_session)
    db.session.commit()

    log_event(g.user.fiscal_id, "Jeton d'administration délivré", "/api/admin/token")

    return jsonify({
        "admin_token": admin_session.token,
        "expires_in_seconds": int(current_app.config["ADMIN_SESSION_LIFETIME"].total_seconds()),
    }), 200


@bp.get("/accounts")
@require_session(scope="admin", roles=("admin",))
def list_accounts():
    users = User.query.order_by(User.created_at.desc()).all()
    log_event(g.user.fiscal_id, "Consultation de la liste des comptes", "/api/admin/accounts")
    return jsonify([u.to_public_dict() for u in users]), 200


@bp.post("/accounts")
@require_session(scope="admin", roles=("admin",))
def create_account():
    data = request.get_json(silent=True) or {}
    fiscal_id = str(data.get("fiscal_id", "")).strip()
    name = str(data.get("name", "")).strip()
    role = str(data.get("role", "external"))
    password = str(data.get("password", ""))

    if not is_fiscal_id_valid(fiscal_id):
        return jsonify({"error": "Numéro fiscal invalide (13 chiffres requis)."}), 400
    if not name:
        return jsonify({"error": "Le nom est obligatoire."}), 400
    if role not in ("external", "agent", "admin"):
        return jsonify({"error": "Rôle invalide."}), 400
    if not is_password_valid(password):
        return jsonify({"error": "Le mot de passe ne respecte pas la politique de sécurité.",
                         "rules": validate_password(password)}), 400
    if User.query.filter_by(fiscal_id=fiscal_id).first():
        return jsonify({"error": "Un compte avec ce numéro fiscal existe déjà."}), 409

    user = User(
        fiscal_id=fiscal_id,
        name=name,
        email=f"{fiscal_id}@dgfip-demo.local",
        password_hash=hash_password(password),
        role=role,
    )
    db.session.add(user)
    db.session.commit()

    log_event(g.user.fiscal_id, f"Création du compte {fiscal_id}", "/api/admin/accounts/create", "high")
    return jsonify(user.to_public_dict()), 201


@bp.put("/accounts/<int:user_id>")
@require_session(scope="admin", roles=("admin",))
def update_account(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    if "name" in data and str(data["name"]).strip():
        user.name = str(data["name"]).strip()
    if "role" in data:
        role = str(data["role"])
        if role not in ("external", "agent", "admin"):
            return jsonify({"error": "Rôle invalide."}), 400
        user.role = role

    db.session.commit()
    log_event(g.user.fiscal_id, f"Modification du compte {user.fiscal_id}", "/api/admin/accounts/update")
    return jsonify(user.to_public_dict()), 200


@bp.post("/accounts/<int:user_id>/reset-password")
@require_session(scope="admin", roles=("admin",))
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}
    new_password = str(data.get("password", ""))

    if not is_password_valid(new_password):
        return jsonify({"error": "Le mot de passe ne respecte pas la politique de sécurité.",
                         "rules": validate_password(new_password)}), 400

    user.password_hash = hash_password(new_password)
    # Invalider les sessions existantes de l'utilisateur après une
    # réinitialisation de mot de passe.
    Session.query.filter_by(user_id=user.id).delete()
    db.session.commit()

    log_event(g.user.fiscal_id, f"Réinitialisation du mot de passe du compte {user.fiscal_id}",
              "/api/admin/accounts/reset-password", "high")
    return jsonify({"ok": True}), 200


@bp.delete("/accounts/<int:user_id>")
@require_session(scope="admin", roles=("admin",))
def delete_account(user_id):
    user = User.query.get_or_404(user_id)
    fiscal_id = user.fiscal_id
    db.session.delete(user)
    db.session.commit()

    log_event(g.user.fiscal_id, f"Suppression du compte {fiscal_id}", "/api/admin/accounts/delete", "high")
    return jsonify({"ok": True}), 200


@bp.get("/logs")
@require_session(scope="admin", roles=("admin",))
def list_logs():
    limit = min(int(request.args.get("limit", 100)), 500)
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return jsonify([entry.to_dict() for entry in logs]), 200
