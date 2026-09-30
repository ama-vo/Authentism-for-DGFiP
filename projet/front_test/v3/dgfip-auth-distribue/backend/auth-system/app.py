"""
Système d'authentification — nœud « Système d'authentification (LDAP) »
du schéma. Seul service qui parle à l'annuaire LDAP et qui détient
l'état des sessions. N'est JAMAIS exposé directement au navigateur :
seule l'Application Web l'appelle (réseau interne).
"""
import os
import secrets

from flask import Flask, jsonify, request
from flask_cors import CORS

from ldap_directory import get_directory
from logging_client import send_log
from store import MFA_MAX_ATTEMPTS, store

app = Flask(__name__)
CORS(app)

INTERNAL_SHARED_SECRET = os.environ.get("INTERNAL_SHARED_SECRET", "dev-internal-secret")
DEBUG_EXPOSE_MFA_CODE = os.environ.get("DEBUG_EXPOSE_MFA_CODE", "false").lower() == "true"

# Pages exposées par l'Application Web et rôles autorisés pour
# chacune — c'est ce que le flux 7/8 (« vérification du rôle... à
# confronter aux rôles autorisés pour l'accès à cette page ») vient
# interroger. /admin.php n'y figure pas : son accès ne passe jamais
# par ce contrôle générique, uniquement par l'échange de jeton dédié
# (flux 10/11).
PAGE_RBAC = {
    "dashboard": {"external", "agent", "admin"},
    "page1": {"agent", "admin"},
}


def _mint_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


def _require_internal_caller():
    if request.headers.get("X-Internal-Secret") != INTERNAL_SHARED_SECRET:
        return jsonify({"error": "Appelant non autorisé."}), 403
    return None


def _send_2fa_email(user, code: str) -> None:
    # Point d'intégration du fournisseur d'e-mail transactionnel réel.
    app.logger.info("[2FA] Envoi du code %s à %s (%s)", code, user.email, user.fiscal_id)


# ---------------------------------------------------------------
# Flux 2/3 : validation des identifiants + flux 4 : envoi du 2FA
# ---------------------------------------------------------------
@app.post("/internal/auth/credentials")
def check_credentials():
    if (err := _require_internal_caller()):
        return err

    data = request.get_json(silent=True) or {}
    fiscal_id = str(data.get("fiscal_id", "")).strip()
    password = str(data.get("password", ""))
    ip = str(data.get("ip", "inconnu"))

    directory = get_directory()
    user = directory.check_credentials(fiscal_id, password)

    if not user:
        send_log(fiscal_id or "inconnu", "Validation LDAP refusée (identifiants invalides)",
                  "/internal/auth/credentials", ip, "normal")
        return jsonify({"error": "Identifiant ou mot de passe incorrect."}), 401

    code = _mint_code()
    pending_token = store.new_pending_mfa(user.fiscal_id, code)
    _send_2fa_email(user, code)

    send_log(user.fiscal_id, "Identifiants validés par LDAP — code 2FA envoyé",
              "/internal/auth/credentials", ip, "normal")

    response = {"pending_token": pending_token, "expires_in_seconds": 300}
    if DEBUG_EXPOSE_MFA_CODE:
        response["debug_code"] = code
    return jsonify(response), 200


# ---------------------------------------------------------------
# Flux 5 : validation du code 2FA (ou terminaison de session)
# ---------------------------------------------------------------
@app.post("/internal/auth/2fa/verify")
def verify_2fa():
    if (err := _require_internal_caller()):
        return err

    data = request.get_json(silent=True) or {}
    pending_token = str(data.get("pending_token", ""))
    code = str(data.get("code", "")).strip()
    ip = str(data.get("ip", "inconnu"))

    pending = store.get_pending_mfa(pending_token)
    if not pending:
        send_log("inconnu", "Terminaison de session (jeton MFA expiré ou inconnu)",
                  "/internal/auth/2fa/verify", ip, "normal")
        return jsonify({"error": "Session d'authentification expirée."}), 400

    if pending.attempts >= MFA_MAX_ATTEMPTS:
        store.consume_pending_mfa(pending_token)
        send_log(pending.fiscal_id, "Terminaison de session (échecs 2FA répétés)",
                  "/internal/auth/2fa/verify", ip, "normal")
        return jsonify({"error": "Nombre maximal de tentatives atteint."}), 429

    if not secrets.compare_digest(pending.code, code):
        attempts = store.register_mfa_failure(pending_token)
        send_log(pending.fiscal_id, "Échec de validation du code 2FA",
                  "/internal/auth/2fa/verify", ip, "normal")
        return jsonify({"error": "Code incorrect.",
                         "attempts_remaining": max(0, MFA_MAX_ATTEMPTS - attempts)}), 401

    directory = get_directory()
    role = directory.get_role(pending.fiscal_id)
    store.consume_pending_mfa(pending_token)
    token = store.new_session(pending.fiscal_id, role, scope="normal")

    send_log(pending.fiscal_id, "Code 2FA validé — session ouverte", "/internal/auth/2fa/verify", ip, "normal")

    return jsonify({"token": token, "role": role, "fiscal_id": pending.fiscal_id}), 200


@app.post("/internal/auth/2fa/resend")
def resend_2fa():
    if (err := _require_internal_caller()):
        return err
    data = request.get_json(silent=True) or {}
    pending_token = str(data.get("pending_token", ""))

    pending = store.get_pending_mfa(pending_token)
    if not pending:
        return jsonify({"error": "Session d'authentification expirée."}), 400

    directory = get_directory()
    user = directory.find_user(pending.fiscal_id)
    code = _mint_code()
    store.replace_pending_code(pending_token, code)
    if user:
        _send_2fa_email(user, code)

    response = {"expires_in_seconds": 300}
    if DEBUG_EXPOSE_MFA_CODE:
        response["debug_code"] = code
    return jsonify(response), 200


# ---------------------------------------------------------------
# Flux 7/8 : vérification du rôle pour une page donnée
# ---------------------------------------------------------------
@app.post("/internal/auth/rbac/check")
def rbac_check():
    if (err := _require_internal_caller()):
        return err

    data = request.get_json(silent=True) or {}
    token = str(data.get("token", ""))
    page = str(data.get("page", ""))
    ip = str(data.get("ip", "inconnu"))

    session = store.get_session(token)
    if not session or session.scope != "normal":
        send_log("inconnu", "Refus RBAC (jeton de session invalide)", f"/{page}.php", ip, "normal")
        return jsonify({"error": "Session invalide."}), 401

    allowed_roles = PAGE_RBAC.get(page)
    if allowed_roles is None:
        return jsonify({"error": "Page inconnue du modèle RBAC."}), 404

    allowed = session.role in allowed_roles
    send_log(
        session.fiscal_id,
        f"Vérification RBAC pour /{page}.php — " + ("autorisé" if allowed else "refusé"),
        f"/{page}.php",
        ip,
        "normal",
    )
    return jsonify({"allowed": allowed, "role": session.role, "fiscal_id": session.fiscal_id}), 200


# ---------------------------------------------------------------
# Flux 10/11 : échange de jeton pour un accès admin scopé /admin.php
# ---------------------------------------------------------------
@app.post("/internal/auth/admin/exchange")
def admin_exchange():
    if (err := _require_internal_caller()):
        return err

    data = request.get_json(silent=True) or {}
    token = str(data.get("token", ""))
    ip = str(data.get("ip", "inconnu"))

    session = store.get_session(token)
    if not session or session.scope != "normal":
        send_log("inconnu", "Refus d'échange de jeton administrateur (session invalide)",
                  "/admin.php", ip, "high")
        return jsonify({"error": "Session invalide."}), 401

    directory = get_directory()
    if not directory.is_admin(session.fiscal_id):
        send_log(session.fiscal_id, "Refus d'échange de jeton administrateur (hors groupe admin LDAP)",
                  "/admin.php", ip, "high")
        return jsonify({"error": "Compte non membre du groupe administrateur."}), 403

    admin_token = store.new_session(
        session.fiscal_id, "admin", scope="admin", scoped_endpoint="/admin.php"
    )
    send_log(session.fiscal_id, "Jeton administrateur scopé délivré (/admin.php uniquement)",
              "/admin.php", ip, "high")

    return jsonify({"admin_token": admin_token, "expires_in_seconds": 600, "scoped_endpoint": "/admin.php"}), 200


# ---------------------------------------------------------------
# Vérification générique d'un jeton (normal ou admin) — utilisée par
# l'Application Web avant de servir chaque page protégée.
# ---------------------------------------------------------------
@app.post("/internal/auth/session/check")
def session_check():
    if (err := _require_internal_caller()):
        return err
    data = request.get_json(silent=True) or {}
    token = str(data.get("token", ""))
    required_scope = str(data.get("scope", "normal"))
    required_endpoint = data.get("endpoint")

    session = store.get_session(token)
    if not session or session.scope != required_scope:
        return jsonify({"valid": False}), 200
    if session.scope == "admin" and required_endpoint and session.scoped_endpoint != required_endpoint:
        return jsonify({"valid": False}), 200

    return jsonify({"valid": True, "fiscal_id": session.fiscal_id, "role": session.role}), 200


@app.post("/internal/auth/logout")
def logout():
    if (err := _require_internal_caller()):
        return err
    data = request.get_json(silent=True) or {}
    token = str(data.get("token", ""))
    ip = str(data.get("ip", "inconnu"))

    session = store.get_session(token)
    store.revoke_session(token)
    if session:
        send_log(session.fiscal_id, "Déconnexion", "/logout", ip, "normal")
    return jsonify({"ok": True}), 200


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "auth-system"}), 200


if __name__ == "__main__":
    # Ce bloc ne sert qu'au lancement local direct (`python app.py`).
    # En conteneur, c'est gunicorn qui sert l'application (voir Dockerfile) —
    # jamais le serveur de développement Flask.
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(port=int(os.environ.get("PORT", 5001)), debug=debug)
