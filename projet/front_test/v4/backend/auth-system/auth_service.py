"""
Système d'authentification — entité « Système d'Authentification » du
schéma (ArchiWebDistribuée.drawio.svg).

Seul service qui parle à l'annuaire LDAP et qui détient l'état des
sessions (dans Redis). N'est JAMAIS exposé au navigateur : seule
l'Application Web l'appelle, sur le réseau interne, en HTTPS, avec le
secret inter-services. Toutes les routes sont donc /internal/*.

Correspondance avec les flux du schéma :
  2/3   validation des identifiants contre LDAP   → /internal/login
  4     envoi du code 2FA par e-mail               → /internal/login, /internal/mfa/resend
  5     validation du code 2FA                     → /internal/mfa/verify
  7/8   vérification du rôle pour une page         → /internal/rbac/check, /internal/dashboard
  10/11 échange de jeton administrateur scopé      → /internal/admin/exchange
  12/13 événements envoyés au puits de logs        → common.logclient.send_log
"""
import functools
import logging
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import Flask, jsonify, request  # noqa: E402

import mailer  # noqa: E402
import store  # noqa: E402
from common import internal  # noqa: E402
from common.logclient import send_log  # noqa: E402
from common.validation import (ValidationError, is_fiscal_id, is_mfa_code, is_token,  # noqa: E402
                               password_problems, require_email, require_fiscal_id, require_label,
                               require_name, require_password, require_role, require_roles, require_slug)
from directory import DirectoryError, get_directory  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("auth-system")

DEBUG_EXPOSE_MFA_CODE = os.environ.get("DEBUG_EXPOSE_MFA_CODE", "false").lower() == "true"
SEED_DEMO_ACCOUNTS = os.environ.get("SEED_DEMO_ACCOUNTS", "true").lower() == "true"
MAX_FAILED_LOGINS = int(os.environ.get("MAX_FAILED_LOGINS", "5"))
LOCKOUT_SECONDS = int(os.environ.get("LOCKOUT_SECONDS", "900"))
IP_MAX_ATTEMPTS = int(os.environ.get("IP_MAX_FAILED_ATTEMPTS", "50"))
IP_WINDOW_SECONDS = 900
GENERIC_LOGIN_ERROR = "Identifiant ou mot de passe incorrect."

app = Flask(__name__)
internal.harden_json_app(app)
internal.assert_production_ready()
if DEBUG_EXPOSE_MFA_CODE and os.environ.get("APP_ENV") == "production":
    raise RuntimeError("DEBUG_EXPOSE_MFA_CODE interdit en production.")


def _bootstrap() -> None:
    """Création idempotente de l'arborescence LDAP, des groupes RBAC, des
    comptes de démonstration et des pages par défaut. Réessaie tant que
    l'annuaire n'est pas prêt."""
    for attempt in range(30):
        try:
            get_directory().ensure_structure(seed_demo=SEED_DEMO_ACCOUNTS)
            store.seed_pages()
            logger.info("Annuaire LDAP et registre des pages initialisés.")
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("Initialisation impossible (tentative %d) : %s", attempt + 1, exc)
            time.sleep(2)
    raise RuntimeError("Impossible d'initialiser l'annuaire LDAP.")


_bootstrap()


# ---------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------
def body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def ip_of(d: dict) -> str:
    return str(d.get("ip", "inconnu"))[:64]


def endpoint_of(d: dict, default: str) -> str:
    return str(d.get("endpoint", default))[:200]


def err(message: str, status: int, **extra):
    return jsonify({"error": message, **extra}), status


@app.errorhandler(DirectoryError)
def _directory_error(exc):
    logger.error("Erreur annuaire : %s", exc)
    return err("Annuaire LDAP indisponible ou opération refusée.", 503)


@app.errorhandler(ValidationError)
def _validation_error(exc):
    return err(str(exc), 400)


def _issue_code(user, purpose: str, code: str) -> None:
    try:
        mailer.send_code(user.email, user.name, code, purpose, store.MFA_CODE_TTL)
    except Exception:  # noqa: BLE001
        # On ne révèle pas le détail ; le code reste valable si le
        # relais revient (renvoi possible).
        logger.exception("Envoi du code impossible")


def _challenge_response(token: str, code: str, email: str | None) -> dict:
    resp = {"challenge_token": token, "expires_in_seconds": store.MFA_CODE_TTL}
    if email:
        resp["sent_to"] = mailer.mask_email(email)
    if DEBUG_EXPOSE_MFA_CODE and email:
        resp["debug_code"] = code
    return resp


# ---------------------------------------------------------------------
# Flux 1 → 2/3 → 4 : identifiants, puis envoi du code 2FA
# ---------------------------------------------------------------------
@app.post("/internal/login")
@internal.internal_only
def login():
    d = body()
    fiscal_id, password, ip = d.get("fiscal_id"), d.get("password"), ip_of(d)

    # Seuls les ÉCHECS comptent : des usagers légitimes derrière une même
    # IP (NAT d'un service) ne sont pas bloqués par les connexions réussies.
    if store.count(f"ip:{ip}") >= IP_MAX_ATTEMPTS:
        send_log(str(fiscal_id)[:13] if is_fiscal_id(fiscal_id) else "inconnu",
                 "Connexion refusée (trop de tentatives depuis cette IP)", "/login.php", ip, "high", "failure")
        return err("Trop de tentatives depuis votre adresse. Réessayez dans quelques minutes.", 429)

    if not is_fiscal_id(fiscal_id) or not isinstance(password, str) or not 0 < len(password) <= 128:
        store.hit(f"ip:{ip}", IP_WINDOW_SECONDS)
        send_log("inconnu", "Tentative de connexion rejetée (format invalide)", "/login.php", ip, "normal", "failure")
        return err(GENERIC_LOGIN_ERROR, 401)

    remaining = store.lock_remaining(fiscal_id)
    if remaining:
        send_log(fiscal_id, "Connexion refusée (compte temporairement verrouillé)", "/login.php", ip, "high", "failure")
        return err(f"Compte temporairement verrouillé suite à des échecs répétés. "
                   f"Réessayez dans {max(1, remaining // 60)} minute(s) ou réinitialisez votre mot de passe.", 423)

    user = get_directory().authenticate(fiscal_id, password)
    if not user:
        store.hit(f"ip:{ip}", IP_WINDOW_SECONDS)
        failures = store.hit(f"fail:{fiscal_id}", LOCKOUT_SECONDS)
        if failures >= MAX_FAILED_LOGINS:
            store.lock_account(fiscal_id, LOCKOUT_SECONDS)
            store.reset_counter(f"fail:{fiscal_id}")
            send_log(fiscal_id, f"Compte verrouillé {LOCKOUT_SECONDS // 60} min après {failures} échecs de connexion",
                     "/login.php", ip, "critical", "failure")
        else:
            send_log(fiscal_id, "Validation LDAP refusée (identifiants invalides)", "/login.php", ip, "normal", "failure")
        return err(GENERIC_LOGIN_ERROR, 401)

    store.reset_counter(f"fail:{fiscal_id}")
    code = store.mint_code()
    token = store.create_challenge(user.fiscal_id, "login", code)
    _issue_code(user, "login", code)
    send_log(user.fiscal_id, "Identifiants validés par LDAP — code 2FA envoyé par e-mail", "/login.php", ip)
    return jsonify(_challenge_response(token, code, user.email)), 200


# ---------------------------------------------------------------------
# Flux 5 : validation du code 2FA, ouverture de session (ou terminaison)
# ---------------------------------------------------------------------
@app.post("/internal/mfa/verify")
@internal.internal_only
def mfa_verify():
    d = body()
    token, code, ip = d.get("challenge_token"), d.get("code"), ip_of(d)

    challenge = store.get_challenge(token, "login") if is_token(token) else None
    if not challenge:
        send_log("inconnu", "Terminaison de session (code 2FA expiré ou inconnu)", "/login.php/verify", ip, "normal", "failure")
        return err("Session d'authentification expirée. Veuillez vous reconnecter.", 400, restart=True)

    fiscal_id = challenge["fiscal_id"]
    if not is_mfa_code(code) or not store.check_code(token, challenge, code):
        attempts = store.register_failure(token)
        remaining = store.MFA_MAX_ATTEMPTS - attempts
        if remaining <= 0:
            send_log(fiscal_id, "Terminaison de session (3 échecs de code 2FA)", "/login.php/verify", ip, "high", "failure")
            return err("Nombre maximal de tentatives atteint. Veuillez vous reconnecter.", 401, restart=True)
        send_log(fiscal_id, "Échec de validation du code 2FA", "/login.php/verify", ip, "normal", "failure")
        return err("Code incorrect.", 401, attempts_remaining=remaining)

    if not store.consume_challenge(token):
        return err("Session d'authentification expirée. Veuillez vous reconnecter.", 400, restart=True)

    directory = get_directory()
    role = directory.get_role(fiscal_id)
    user = directory.find_user(fiscal_id)
    if not role or not user:
        send_log(fiscal_id, "Ouverture de session refusée (aucun rôle LDAP)", "/login.php/verify", ip, "high", "failure")
        return err("Aucun rôle n'est attribué à ce compte. Contactez un administrateur.", 403)

    session_token = store.create_session(fiscal_id, role, user.name)
    send_log(fiscal_id, f"Code 2FA validé — session ouverte (rôle {role})", "/login.php/verify", ip)
    return jsonify({"session_token": session_token, "fiscal_id": fiscal_id, "role": role, "name": user.name,
                    "expires_in": store.SESSION_IDLE_TTL}), 200


@app.post("/internal/mfa/resend")
@internal.internal_only
def mfa_resend():
    d = body()
    token, ip = d.get("challenge_token"), ip_of(d)
    purpose = "reset" if d.get("purpose") == "reset" else "login"
    challenge = store.get_challenge(token, purpose) if is_token(token) else None
    if not challenge:
        return err("Session d'authentification expirée. Veuillez recommencer.", 400, restart=True)

    code = store.mint_code()
    if store.replace_code(token, code) is None:
        send_log(challenge["fiscal_id"] or "inconnu", "Renvoi de code refusé (limite atteinte)",
                 endpoint_of(d, "/login.php/resend"), ip, "high", "failure")
        return err("Nombre maximal de renvois atteint. Veuillez recommencer.", 429, restart=True)

    user = get_directory().find_user(challenge["fiscal_id"]) if challenge["fiscal_id"] else None
    if user:
        _issue_code(user, purpose, code)
        send_log(user.fiscal_id, "Nouveau code envoyé par e-mail", endpoint_of(d, "/login.php/resend"), ip)
    return jsonify(_challenge_response(token, code, user.email if user else None)), 200


# ---------------------------------------------------------------------
# Réinitialisation de son propre mot de passe (page d'authentification)
# ---------------------------------------------------------------------
@app.post("/internal/password/forgot")
@internal.internal_only
def password_forgot():
    d = body()
    fiscal_id, ip = d.get("fiscal_id"), ip_of(d)
    if not is_fiscal_id(fiscal_id):
        return err("Le numéro fiscal doit comporter exactement 13 chiffres.", 400)
    if store.hit(f"forgot-ip:{ip}", IP_WINDOW_SECONDS) > 10 or store.hit(f"forgot:{fiscal_id}", IP_WINDOW_SECONDS) > 3:
        send_log(fiscal_id, "Demande de réinitialisation refusée (trop de demandes)", "/password/forgot", ip, "high", "failure")
        return err("Trop de demandes. Réessayez dans quelques minutes.", 429)

    user = get_directory().find_user(fiscal_id)
    code = store.mint_code()
    # Compte inconnu : on renvoie quand même un jeton (inutilisable) pour
    # ne pas révéler quels numéros fiscaux existent.
    token = store.create_challenge(user.fiscal_id if user else "", "reset", code)
    if user:
        _issue_code(user, "reset", code)
        send_log(fiscal_id, "Demande de réinitialisation de mot de passe — code envoyé", "/password/forgot", ip, "high")
    else:
        send_log(fiscal_id, "Demande de réinitialisation pour un compte inexistant", "/password/forgot", ip, "normal", "failure")
    resp = _challenge_response(token, code, user.email if user else None)
    resp.pop("sent_to", None)
    resp["message"] = "Si ce numéro fiscal correspond à un compte, un code a été envoyé à l'adresse e-mail associée."
    return jsonify(resp), 200


@app.post("/internal/password/reset")
@internal.internal_only
def password_reset():
    d = body()
    token, code, new_password, ip = d.get("challenge_token"), d.get("code"), d.get("new_password"), ip_of(d)

    challenge = store.get_challenge(token, "reset") if is_token(token) else None
    if not challenge:
        return err("Demande expirée. Veuillez recommencer.", 400, restart=True)
    problems = password_problems(new_password)
    if problems:
        return err("Mot de passe non conforme : " + ", ".join(problems) + ".", 400)

    fiscal_id = challenge["fiscal_id"]
    if not fiscal_id or not is_mfa_code(code) or not store.check_code(token, challenge, code):
        attempts = store.register_failure(token)
        remaining = store.MFA_MAX_ATTEMPTS - attempts
        send_log(fiscal_id or "inconnu", "Échec du code de réinitialisation", "/password/reset", ip, "high", "failure")
        if remaining <= 0:
            return err("Nombre maximal de tentatives atteint. Veuillez recommencer.", 401, restart=True)
        return err("Code incorrect.", 401, attempts_remaining=remaining)

    if not store.consume_challenge(token):
        return err("Demande expirée. Veuillez recommencer.", 400, restart=True)

    get_directory().set_password(fiscal_id, new_password)
    revoked = store.revoke_all(fiscal_id)
    store.unlock_account(fiscal_id)
    send_log(fiscal_id, f"Mot de passe réinitialisé par l'utilisateur ({revoked} session(s) révoquée(s))",
             "/password/reset", ip, "high")
    return jsonify({"ok": True}), 200


# ---------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------
@app.post("/internal/session")
@internal.internal_only
def session_info():
    d = body()
    s = store.get_session(d.get("session_token") or "")
    if not s:
        return err("Session invalide ou expirée.", 401)
    return jsonify({"fiscal_id": s["fiscal_id"], "role": s["role"], "name": s["name"],
                    "expires_in": s["expires_in"]}), 200


@app.post("/internal/logout")
@internal.internal_only
def logout():
    d = body()
    ip = ip_of(d)
    data = store.revoke_session(d.get("session_token") or "")
    if d.get("admin_token"):
        store.revoke_session(d["admin_token"])
    if data:
        send_log(data.get("fiscal_id"), "Déconnexion — session révoquée", "/logout", ip)
    return jsonify({"ok": True}), 200


# ---------------------------------------------------------------------
# Flux 6 → 7/8 → 9 : tableau de bord et contrôle RBAC par page
# ---------------------------------------------------------------------
def _session_and_role(d: dict, endpoint: str):
    s = store.get_session(d.get("session_token") or "")
    if not s:
        send_log("inconnu", "Accès refusé (session invalide ou expirée)", endpoint, ip_of(d), "normal", "failure")
        return None, None
    # Flux 7 : le rôle fait foi dans l'annuaire LDAP, pas dans le jeton.
    role = get_directory().get_role(s["fiscal_id"])
    return s, role


@app.post("/internal/dashboard")
@internal.internal_only
def dashboard():
    d = body()
    s, role = _session_and_role(d, "/dashboard.php")
    if not s:
        return err("Session invalide ou expirée.", 401)
    if not role:
        return err("Aucun rôle attribué.", 403)

    links = [{
        "slug": p["slug"], "label": p["label"], "description": p.get("description", ""),
        "endpoint": f"/{p['slug']}.php", "allowed": role in p["roles"],
    } for p in store.list_pages() if p.get("visible", True)]
    links.append({"slug": "admin", "label": "Panneau d'administration",
                  "description": "Gestion des comptes, des pages et du journal de traçabilité.",
                  "endpoint": "/admin.php", "allowed": role == "admin"})
    send_log(s["fiscal_id"], "Consultation du tableau de bord", "/dashboard.php", ip_of(d))
    return jsonify({"fiscal_id": s["fiscal_id"], "name": s["name"], "role": role, "links": links}), 200


@app.post("/internal/rbac/check")
@internal.internal_only
def rbac_check():
    d = body()
    slug = d.get("page")
    endpoint = f"/{slug}.php" if isinstance(slug, str) and len(slug) < 40 else "/?.php"
    s, role = _session_and_role(d, endpoint)
    if not s:
        return err("Session invalide ou expirée.", 401)

    page = store.get_page(slug) if isinstance(slug, str) else None
    if not page:
        send_log(s["fiscal_id"], "Accès refusé (endpoint hors liste d'autorisation)", endpoint, ip_of(d), "high", "failure")
        return err("Page inconnue.", 404)

    allowed = bool(role) and role in page["roles"]
    if allowed:
        send_log(s["fiscal_id"], f"Vérification RBAC — accès autorisé (rôle {role})", endpoint, ip_of(d))
        return jsonify({"allowed": True, "role": role, "page": page}), 200
    send_log(s["fiscal_id"], f"Vérification RBAC — accès refusé (rôle {role})", endpoint, ip_of(d), "high", "failure")
    return jsonify({"allowed": False, "role": role}), 200


# ---------------------------------------------------------------------
# Flux 10/11 : échange du jeton de session contre un jeton admin scopé
# ---------------------------------------------------------------------
@app.post("/internal/admin/exchange")
@internal.internal_only
def admin_exchange():
    d = body()
    ip = ip_of(d)
    session_token = d.get("session_token") or ""
    s = store.get_session(session_token)
    if not s:
        send_log("inconnu", "Échange de jeton administrateur refusé (session invalide)", "/admin.php/token", ip, "high", "failure")
        return err("Session invalide ou expirée.", 401)

    fiscal_id = s["fiscal_id"]
    directory = get_directory()
    if not directory.is_admin(fiscal_id):
        send_log(fiscal_id, "Échange de jeton administrateur refusé (hors groupe LDAP admins)",
                 "/admin.php/token", ip, "high", "failure")
        return err("Votre compte n'appartient pas au groupe administrateur.", 403)

    if store.hit(f"admin-reauth:{fiscal_id}", 900) > 5:
        send_log(fiscal_id, "Échange de jeton administrateur bloqué (trop d'essais)", "/admin.php/token", ip, "critical", "failure")
        return err("Trop de tentatives. Réessayez plus tard.", 429)

    # Ré-authentification (« step-up ») : le mot de passe est redemandé
    # avant de délivrer des droits d'administration.
    password = d.get("password")
    if not isinstance(password, str) or not directory.authenticate(fiscal_id, password):
        send_log(fiscal_id, "Échange de jeton administrateur refusé (ré-authentification échouée)",
                 "/admin.php/token", ip, "high", "failure")
        return err("Mot de passe incorrect.", 401)

    store.reset_counter(f"admin-reauth:{fiscal_id}")
    admin_token = store.create_session(fiscal_id, "admin", s["name"], scope="admin",
                                       parent=s["hash"], scoped_endpoint="/admin.php")
    send_log(fiscal_id, "Jeton administrateur scopé délivré (/admin.php uniquement)", "/admin.php/token", ip, "high")
    return jsonify({"admin_token": admin_token, "expires_in": store.ADMIN_SESSION_TTL,
                    "scoped_endpoint": "/admin.php"}), 200


def admin_required(view):
    """Toute opération d'administration exige : une session normale
    valide + un jeton admin valide, issu de CETTE session, scopé à
    /admin.php, et l'appartenance toujours actuelle au groupe LDAP
    admins. Vérifié ici, pas seulement dans l'Application Web."""
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        d = body()
        endpoint = endpoint_of(d, "/admin.php")
        s = store.get_session(d.get("session_token") or "")
        a = store.get_session(d.get("admin_token") or "", scope="admin")
        valid = (s and a and a["parent"] == s["hash"] and a["fiscal_id"] == s["fiscal_id"]
                 and a["scoped_endpoint"] == "/admin.php" and get_directory().is_admin(s["fiscal_id"]))
        if not valid:
            send_log(s["fiscal_id"] if s else "inconnu", "Accès administration refusé (jeton admin absent, expiré ou invalide)",
                     endpoint, ip_of(d), "high", "failure")
            return err("Jeton d'administration invalide ou expiré.", 403, admin_token_required=True)
        return view(d, s, a, *args, **kwargs)

    return wrapper


@app.post("/internal/admin/check")
@internal.internal_only
@admin_required
def admin_check(d, s, a):
    send_log(s["fiscal_id"], "Accès au panneau d'administration", "/admin.php", ip_of(d), "high")
    return jsonify({"fiscal_id": s["fiscal_id"], "name": s["name"], "expires_in": a["expires_in"]}), 200


@app.post("/internal/admin/users/list")
@internal.internal_only
@admin_required
def admin_users_list(d, s, a):
    users = get_directory().list_users()
    for u in users:
        u["locked"] = store.lock_remaining(u["fiscal_id"]) > 0
        u["active_sessions"] = store.count_sessions(u["fiscal_id"])
    return jsonify(users), 200


@app.post("/internal/admin/users/create")
@internal.internal_only
@admin_required
def admin_users_create(d, s, a):
    fiscal_id = require_fiscal_id(d.get("fiscal_id"))
    name = require_name(d.get("name"))
    email = require_email(d.get("email"))
    role = require_role(d.get("role"))
    password = require_password(d.get("password"))
    directory = get_directory()
    if directory.find_user(fiscal_id):
        return err("Un compte existe déjà avec ce numéro fiscal.", 409)
    directory.create_user(fiscal_id, name, email, role, password)
    send_log(s["fiscal_id"], f"Création du compte {fiscal_id} (rôle {role})", "/admin.php/users", ip_of(d), "critical")
    return jsonify({"ok": True}), 201


@app.post("/internal/admin/users/update")
@internal.internal_only
@admin_required
def admin_users_update(d, s, a):
    fiscal_id = require_fiscal_id(d.get("fiscal_id"))
    directory = get_directory()
    if not directory.find_user(fiscal_id):
        return err("Compte introuvable.", 404)
    name = require_name(d["name"]) if d.get("name") else None
    email = require_email(d["email"]) if d.get("email") else None
    role = require_role(d["role"]) if d.get("role") else None

    if role and fiscal_id == s["fiscal_id"] and role != "admin":
        return err("Vous ne pouvez pas retirer vos propres droits d'administration.", 400)

    directory.update_user(fiscal_id, name, email)
    changes = [c for c, v in (("nom", name), ("e-mail", email)) if v]
    if role:
        previous = directory.get_role(fiscal_id)
        if previous != role:
            directory.set_role(fiscal_id, role)
            revoked = store.revoke_all(fiscal_id)
            changes.append(f"rôle {previous} → {role}, {revoked} session(s) révoquée(s)")
            send_log(s["fiscal_id"], f"Modification des accès du compte {fiscal_id} : {previous} → {role}",
                     "/admin.php/users", ip_of(d), "critical")
    if d.get("unlock"):
        store.unlock_account(fiscal_id)
        changes.append("déverrouillage")
    if changes:
        send_log(s["fiscal_id"], f"Modification du compte {fiscal_id} ({', '.join(changes)})",
                 "/admin.php/users", ip_of(d), "critical")
    return jsonify({"ok": True}), 200


@app.post("/internal/admin/users/password")
@internal.internal_only
@admin_required
def admin_users_password(d, s, a):
    fiscal_id = require_fiscal_id(d.get("fiscal_id"))
    password = require_password(d.get("new_password"))
    directory = get_directory()
    if not directory.find_user(fiscal_id):
        return err("Compte introuvable.", 404)
    directory.set_password(fiscal_id, password)
    store.unlock_account(fiscal_id)
    revoked = 0 if fiscal_id == s["fiscal_id"] else store.revoke_all(fiscal_id)
    send_log(s["fiscal_id"], f"Modification du mot de passe du compte {fiscal_id} ({revoked} session(s) révoquée(s))",
             "/admin.php/users", ip_of(d), "critical")
    return jsonify({"ok": True}), 200


@app.post("/internal/admin/users/delete")
@internal.internal_only
@admin_required
def admin_users_delete(d, s, a):
    fiscal_id = require_fiscal_id(d.get("fiscal_id"))
    if fiscal_id == s["fiscal_id"]:
        return err("Vous ne pouvez pas supprimer votre propre compte.", 400)
    directory = get_directory()
    if not directory.find_user(fiscal_id):
        return err("Compte introuvable.", 404)
    directory.delete_user(fiscal_id)
    store.revoke_all(fiscal_id)
    store.unlock_account(fiscal_id)
    send_log(s["fiscal_id"], f"Suppression du compte {fiscal_id}", "/admin.php/users", ip_of(d), "critical")
    return jsonify({"ok": True}), 200


@app.post("/internal/admin/pages/list")
@internal.internal_only
@admin_required
def admin_pages_list(d, s, a):
    return jsonify(store.list_pages()), 200


@app.post("/internal/admin/pages/save")
@internal.internal_only
@admin_required
def admin_pages_save(d, s, a):
    slug = require_slug(d.get("slug"))
    existing = store.get_page(slug)
    if d.get("create") and existing:
        return err("Une page existe déjà avec cet identifiant.", 409)
    if not d.get("create") and not existing:
        return err("Page introuvable.", 404)
    page = {
        "slug": slug,
        "label": require_label(d.get("label"), "Libellé"),
        "description": require_label(d.get("description") or "—", "Description", 200),
        "content": require_label(d.get("content") or "—", "Contenu", 2000),
        "roles": require_roles(d.get("roles")),
        "visible": bool(d.get("visible", True)),
    }
    store.save_page(page)
    verb = "Création" if not existing else "Modification"
    send_log(s["fiscal_id"], f"{verb} de la page /{slug}.php (rôles : {', '.join(page['roles'])}, "
             f"{'visible' if page['visible'] else 'masquée'})", "/admin.php/pages", ip_of(d), "critical")
    return jsonify(page), 200


@app.post("/internal/admin/pages/delete")
@internal.internal_only
@admin_required
def admin_pages_delete(d, s, a):
    slug = require_slug(d.get("slug"))
    if not store.delete_page(slug):
        return err("Page introuvable.", 404)
    send_log(s["fiscal_id"], f"Suppression de la page /{slug}.php", "/admin.php/pages", ip_of(d), "critical")
    return jsonify({"ok": True}), 200


@app.get("/health")
def health():
    ok = store.ping()
    return jsonify({"status": "ok" if ok else "degraded", "service": "auth-system", "redis": ok}), 200 if ok else 503


if __name__ == "__main__":
    internal.run_dev_server(app, 5001)
