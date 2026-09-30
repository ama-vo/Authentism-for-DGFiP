"""
Application Web — nœud « Application Web » du schéma. Expose les
endpoints publics (/login.php, /dashboard.php, /page1.php, /admin.php)
mais ne contient AUCUNE logique d'authentification : elle relaie
chaque décision au Système d'authentification et ne fait que
transmettre au navigateur le jeton opaque qu'il lui renvoie.
"""
import os

from flask import Flask, jsonify, request
from flask_cors import CORS

import auth_client
from auth_client import AuthSystemError

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")}})


def client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else (request.remote_addr or "inconnu")


def bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    return header[7:] if header.startswith("Bearer ") else None


def handle_auth_error(exc: AuthSystemError):
    return jsonify({"error": exc.message}), exc.status


# ---------------------------------------------------------------
# Flux 1 : POST /login.php avec combo login/password
# ---------------------------------------------------------------
@app.post("/login.php")
def login():
    data = request.get_json(silent=True) or {}
    fiscal_id = str(data.get("fiscal_id", "")).strip()
    password = str(data.get("password", ""))

    try:
        result = auth_client.check_credentials(fiscal_id, password, client_ip())
    except AuthSystemError as exc:
        return handle_auth_error(exc)

    return jsonify(result), 200


@app.post("/login.php/verify")
def login_verify_2fa():
    """Flux 5/6 : validation du code 2FA puis redirection logique vers
    /dashboard.php (ici : le front navigue lui-même une fois le jeton
    de session reçu)."""
    data = request.get_json(silent=True) or {}
    pending_token = str(data.get("pending_token", ""))
    code = str(data.get("code", ""))

    try:
        result = auth_client.verify_2fa(pending_token, code, client_ip())
    except AuthSystemError as exc:
        return handle_auth_error(exc)

    return jsonify({**result, "redirect": "/dashboard.php"}), 200


@app.post("/login.php/resend")
def login_resend_2fa():
    data = request.get_json(silent=True) or {}
    pending_token = str(data.get("pending_token", ""))
    try:
        result = auth_client.resend_2fa(pending_token)
    except AuthSystemError as exc:
        return handle_auth_error(exc)
    return jsonify(result), 200


@app.post("/logout")
def logout():
    token = bearer_token()
    if not token:
        return jsonify({"ok": True}), 200
    try:
        auth_client.logout(token, client_ip())
    except AuthSystemError:
        pass
    return jsonify({"ok": True}), 200


# ---------------------------------------------------------------
# Flux 6/7/8/9 : /dashboard.php liste les endpoints accessibles,
# chacun étant vérifié via le modèle RBAC (LDAP)
# ---------------------------------------------------------------
@app.get("/dashboard.php")
def dashboard():
    token = bearer_token()
    if not token:
        return jsonify({"error": "Authentification requise."}), 401

    try:
        rbac = auth_client.rbac_check(token, "dashboard", client_ip())
    except AuthSystemError as exc:
        return handle_auth_error(exc)

    if not rbac["allowed"]:
        return jsonify({"error": "Accès refusé."}), 403

    role = rbac["role"]
    links = [{"endpoint": "/dashboard.php", "label": "Tableau de bord", "allowed": True}]
    for page, label in (("page1", "Tout autre endpoint (exemple)"),):
        try:
            check = auth_client.rbac_check(token, page, client_ip())
            links.append({"endpoint": f"/{page}.php", "label": label, "allowed": check["allowed"]})
        except AuthSystemError:
            links.append({"endpoint": f"/{page}.php", "label": label, "allowed": False})
    links.append({"endpoint": "/admin.php", "label": "Panneau d'administration", "allowed": role == "admin"})

    return jsonify({"fiscal_id": rbac["fiscal_id"], "role": role, "links": links}), 200


# ---------------------------------------------------------------
# Flux 9 : « tout autre endpoint », soumis au même contrôle RBAC
# ---------------------------------------------------------------
@app.get("/page1.php")
def page1():
    token = bearer_token()
    if not token:
        return jsonify({"error": "Authentification requise."}), 401
    try:
        rbac = auth_client.rbac_check(token, "page1", client_ip())
    except AuthSystemError as exc:
        return handle_auth_error(exc)
    if not rbac["allowed"]:
        return jsonify({"error": "Accès refusé."}), 403
    return jsonify({"page": "page1", "content": "Contenu de la page, accessible aux agents et administrateurs."}), 200


# ---------------------------------------------------------------
# Flux 10/11 : échange du jeton de session contre un jeton
# administrateur scopé, avant d'autoriser /admin.php
# ---------------------------------------------------------------
@app.post("/admin.php/token")
def admin_get_token():
    token = bearer_token()
    if not token:
        return jsonify({"error": "Authentification requise."}), 401
    try:
        result = auth_client.admin_exchange(token, client_ip())
    except AuthSystemError as exc:
        return handle_auth_error(exc)
    return jsonify(result), 200


@app.get("/admin.php")
def admin_page():
    admin_token = bearer_token()
    if not admin_token:
        return jsonify({"error": "Jeton d'administration requis."}), 401
    try:
        check = auth_client.session_check(admin_token, scope="admin", endpoint="/admin.php")
    except AuthSystemError as exc:
        return handle_auth_error(exc)
    if not check.get("valid"):
        return jsonify({"error": "Jeton d'administration invalide, expiré ou hors périmètre."}), 403

    return jsonify({
        "fiscal_id": check["fiscal_id"],
        "message": "Bienvenue sur le panneau d'administration.",
    }), 200


@app.get("/admin.php/logs")
def admin_logs():
    """Consultation du journal de traçabilité — réservée au jeton
    administrateur scopé (mêmes règles d'accès que /admin.php)."""
    admin_token = bearer_token()
    if not admin_token:
        return jsonify({"error": "Jeton d'administration requis."}), 401
    try:
        check = auth_client.session_check(admin_token, scope="admin", endpoint="/admin.php")
    except AuthSystemError as exc:
        return handle_auth_error(exc)
    if not check.get("valid"):
        return jsonify({"error": "Jeton d'administration invalide, expiré ou hors périmètre."}), 403

    try:
        logs = auth_client.fetch_logs(limit=int(request.args.get("limit", 100)))
    except AuthSystemError as exc:
        return handle_auth_error(exc)
    return jsonify(logs), 200


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "webapp"}), 200


if __name__ == "__main__":
    # Ce bloc ne sert qu'au lancement local direct (`python app.py`).
    # En conteneur, c'est gunicorn qui sert l'application (voir Dockerfile) —
    # jamais le serveur de développement Flask.
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(port=int(os.environ.get("PORT", 5000)), debug=debug)
