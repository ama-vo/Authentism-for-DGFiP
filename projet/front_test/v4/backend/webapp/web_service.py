"""
Application Web — entité « Application Web » du schéma.

Seul service joignable par le frontend (via Nginx). Ne contient AUCUNE
logique d'authentification : chaque décision est déléguée au Système
d'authentification. Son rôle propre :

1. Liste d'autorisation des endpoints (cahier des charges §2.5) :
   chaque route est déclarée avec son niveau d'accès (@access). Une
   route sans déclaration, ou une URL inconnue, est refusée et le refus
   est journalisé. C'est un modèle « refus par défaut ».
2. Gestion des cookies : les jetons opaques délivrés par le Système
   d'authentification sont placés dans des cookies HttpOnly, Secure,
   SameSite=Strict — jamais accessibles au JavaScript (protection XSS).
3. Protection CSRF : toute requête modifiant l'état doit porter
   l'en-tête X-Requested-With (impossible à poser depuis un autre site
   sans CORS, que l'on n'autorise pas) et une origine valide.
"""
import functools
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import Flask, g, jsonify, request  # noqa: E402

from common import internal  # noqa: E402
from common.logclient import send_log  # noqa: E402
from common.validation import SLUG_RE, bounded_int, is_fiscal_id  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

AUTH_SYSTEM_URL = os.environ.get("AUTH_SYSTEM_URL", "http://127.0.0.1:5001")
LOG_COLLECTOR_URL = os.environ.get("LOG_COLLECTOR_URL", "http://127.0.0.1:5002")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
TRUST_PROXY = os.environ.get("TRUST_PROXY", "true").lower() == "true"
ALLOWED_ORIGINS = {o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()}

# Le préfixe __Host- impose Secure + Path=/ + pas de Domain : le cookie
# ne peut être ni posé ni écrasé par un sous-domaine.
SESSION_COOKIE = "__Host-dgfip_session" if COOKIE_SECURE else "dgfip_session"
ADMIN_COOKIE = "__Host-dgfip_admin" if COOKIE_SECURE else "dgfip_admin"

PUBLIC, SESSION, ADMIN = "public", "session", "admin"

app = Flask(__name__)
internal.harden_json_app(app)
internal.assert_production_ready()

ACCESS: dict[str, str] = {}


def access(level: str):
    """Déclare le niveau d'accès d'une route (entrée de la whitelist)."""
    def decorator(view):
        ACCESS[view.__name__] = level
        return view
    return decorator


def client_ip() -> str:
    if TRUST_PROXY:
        # X-Real-IP est posé par NOTRE Nginx ($remote_addr) et écrase
        # toute valeur fournie par le client. On n'utilise pas le premier
        # élément de X-Forwarded-For, falsifiable par le client.
        real = request.headers.get("X-Real-IP")
        if real:
            return real[:64]
    return (request.remote_addr or "inconnu")[:64]


def origin_allowed(origin: str) -> bool:
    """Contrôle d'origine (anti-CSRF) : la requête doit venir de la page
    servie par ce même site, quelle que soit l'adresse utilisée pour
    l'atteindre (localhost, 127.0.0.1, nom de la machine, port…).
    ALLOWED_ORIGINS permet d'autoriser des origines supplémentaires."""
    if origin in ALLOWED_ORIGINS:
        return True
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme) if TRUST_PROXY else request.scheme
    return origin == f"{scheme}://{request.host}"


def body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def auth(path: str, payload: dict | None = None):
    payload = dict(payload or {})
    payload.setdefault("ip", client_ip())
    return internal.call(AUTH_SYSTEM_URL, "POST", path, payload)


def tokens() -> dict:
    return {"session_token": request.cookies.get(SESSION_COOKIE, ""),
            "admin_token": request.cookies.get(ADMIN_COOKIE, "")}


def deny(message: str, status: int, action: str, priority: str = "high", account: str = "inconnu"):
    send_log(account, action, request.path, client_ip(), priority, "failure")
    return jsonify({"error": message}), status


def set_cookie(resp, name: str, value: str, max_age: int | None = None):
    resp.set_cookie(name, value, max_age=max_age, secure=COOKIE_SECURE, httponly=True,
                    samesite="Strict", path="/")


def clear_cookie(resp, name: str):
    resp.set_cookie(name, "", max_age=0, expires=0, secure=COOKIE_SECURE, httponly=True,
                    samesite="Strict", path="/")


@app.errorhandler(internal.ServiceError)
def _service_error(exc: internal.ServiceError):
    payload = {k: v for k, v in exc.payload.items() if k != "error"}
    resp = jsonify({"error": exc.message, **payload})
    resp.status_code = exc.status
    if exc.status == 401 and request.cookies.get(SESSION_COOKIE) and request.path not in ("/admin.php/token",):
        clear_cookie(resp, SESSION_COOKIE)
        clear_cookie(resp, ADMIN_COOKIE)
    if exc.payload.get("admin_token_required"):
        clear_cookie(resp, ADMIN_COOKIE)
    return resp


# ---------------------------------------------------------------------
# Contrôle d'accès générique : whitelist + CSRF + session
# ---------------------------------------------------------------------
@app.before_request
def enforce_whitelist():
    level = ACCESS.get(request.endpoint or "")
    if request.url_rule is None or level is None:
        if request.path == "/health":
            return None
        return deny("Endpoint non autorisé.", 404, f"Accès refusé : {request.method} hors liste d'autorisation")

    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if request.headers.get("X-Requested-With") != "fetch":
            return deny("Requête refusée (protection CSRF).", 403, "Requête refusée : en-tête anti-CSRF absent")
        origin = request.headers.get("Origin")
        if origin and not origin_allowed(origin):
            return deny("Origine non autorisée.", 403, f"Requête refusée : origine {origin[:80]} non autorisée")

    if level in (SESSION, ADMIN):
        t = tokens()
        if not t["session_token"]:
            return deny("Authentification requise.", 401, "Accès refusé : aucune session", "normal")
        info = auth("/internal/session", {"session_token": t["session_token"]})
        g.user = info
        if level == ADMIN and not t["admin_token"]:
            return deny("Jeton d'administration requis.", 403, "Accès administration refusé : jeton admin absent",
                        "high", info["fiscal_id"])
    return None


# ---------------------------------------------------------------------
# Flux 1 → 5 : connexion + 2FA
# ---------------------------------------------------------------------
@app.post("/login.php")
@access(PUBLIC)
def login():
    d = body()
    return jsonify(auth("/internal/login", {"fiscal_id": d.get("fiscal_id"), "password": d.get("password")})), 200


@app.post("/login.php/verify")
@access(PUBLIC)
def login_verify():
    d = body()
    result = auth("/internal/mfa/verify", {"challenge_token": d.get("challenge_token"), "code": d.get("code")})
    # Flux 6 : redirection vers le tableau de bord (le frontend navigue).
    resp = jsonify({"fiscal_id": result["fiscal_id"], "role": result["role"], "name": result["name"],
                    "redirect": "/dashboard.php"})
    set_cookie(resp, SESSION_COOKIE, result["session_token"])
    clear_cookie(resp, ADMIN_COOKIE)
    return resp, 200


@app.post("/login.php/resend")
@access(PUBLIC)
def login_resend():
    d = body()
    return jsonify(auth("/internal/mfa/resend", {"challenge_token": d.get("challenge_token"), "purpose": "login",
                                                 "endpoint": "/login.php/resend"})), 200


# ---------------------------------------------------------------------
# Réinitialisation de son mot de passe (RBAC : tous les rôles)
# ---------------------------------------------------------------------
@app.post("/password/forgot")
@access(PUBLIC)
def password_forgot():
    return jsonify(auth("/internal/password/forgot", {"fiscal_id": body().get("fiscal_id")})), 200


@app.post("/password/resend")
@access(PUBLIC)
def password_resend():
    d = body()
    result = auth("/internal/mfa/resend", {"challenge_token": d.get("challenge_token"), "purpose": "reset",
                                           "endpoint": "/password/resend"})
    result.pop("sent_to", None)
    return jsonify(result), 200


@app.post("/password/reset")
@access(PUBLIC)
def password_reset():
    d = body()
    auth("/internal/password/reset", {"challenge_token": d.get("challenge_token"), "code": d.get("code"),
                                      "new_password": d.get("new_password")})
    resp = jsonify({"ok": True})
    clear_cookie(resp, SESSION_COOKIE)
    clear_cookie(resp, ADMIN_COOKIE)
    return resp, 200


# ---------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------
@app.get("/session")
@access(SESSION)
def session_info():
    return jsonify(g.user), 200


@app.post("/logout")
@access(PUBLIC)
def logout():
    t = tokens()
    if t["session_token"]:
        try:
            auth("/internal/logout", t)
        except internal.ServiceError:
            pass
    resp = jsonify({"ok": True})
    clear_cookie(resp, SESSION_COOKIE)
    clear_cookie(resp, ADMIN_COOKIE)
    return resp, 200


# ---------------------------------------------------------------------
# Flux 6 → 9 : tableau de bord et pages standard
# ---------------------------------------------------------------------
@app.get("/dashboard.php")
@access(SESSION)
def dashboard():
    return jsonify(auth("/internal/dashboard", {"session_token": tokens()["session_token"]})), 200


@app.get("/<slug>.php")
@access(SESSION)
def standard_page(slug: str):
    if not SLUG_RE.fullmatch(slug):
        return deny("Endpoint non autorisé.", 404, "Accès refusé : endpoint hors liste d'autorisation",
                    account=g.user["fiscal_id"])
    result = auth("/internal/rbac/check", {"session_token": tokens()["session_token"], "page": slug})
    if not result.get("allowed"):
        return jsonify({"error": "Accès refusé : votre rôle ne permet pas d'accéder à cette page."}), 403
    page = result["page"]
    return jsonify({"slug": page["slug"], "label": page["label"], "description": page.get("description", ""),
                    "content": page.get("content", ""), "role": result["role"]}), 200


# ---------------------------------------------------------------------
# Flux 10/11 : échange de jeton, puis administration
# ---------------------------------------------------------------------
@app.post("/admin.php/token")
@access(SESSION)
def admin_token():
    result = auth("/internal/admin/exchange", {"session_token": tokens()["session_token"],
                                               "password": body().get("password")})
    resp = jsonify({"expires_in": result["expires_in"], "scoped_endpoint": result["scoped_endpoint"]})
    set_cookie(resp, ADMIN_COOKIE, result["admin_token"], max_age=result["expires_in"])
    return resp, 200


def admin_call(path: str, extra: dict | None = None, endpoint: str | None = None):
    payload = {**tokens(), **(extra or {}), "endpoint": endpoint or request.path}
    return auth(path, payload)


@app.get("/admin.php")
@access(ADMIN)
def admin_home():
    return jsonify(admin_call("/internal/admin/check")), 200


@app.post("/admin.php/logout")
@access(ADMIN)
def admin_logout():
    try:
        internal.call(AUTH_SYSTEM_URL, "POST", "/internal/logout",
                      {"session_token": "", "admin_token": tokens()["admin_token"], "ip": client_ip()})
    except internal.ServiceError:
        pass
    resp = jsonify({"ok": True})
    clear_cookie(resp, ADMIN_COOKIE)
    return resp, 200


@app.get("/admin.php/logs")
@access(ADMIN)
def admin_logs():
    admin_call("/internal/admin/check", endpoint="/admin.php/logs")
    params = {"limit": bounded_int(request.args.get("limit"), 200, 1, 1000)}
    if request.args.get("priority") in ("normal", "high", "critical"):
        params["priority"] = request.args["priority"]
    if is_fiscal_id(request.args.get("account", "")):
        params["account"] = request.args["account"]
    if request.args.get("order") == "time":
        params["order"] = "time"
    return jsonify(internal.call(LOG_COLLECTOR_URL, "GET", "/logs", params=params)), 200


@app.get("/admin.php/logs/verify")
@access(ADMIN)
def admin_logs_verify():
    admin_call("/internal/admin/check", endpoint="/admin.php/logs/verify")
    return jsonify(internal.call(LOG_COLLECTOR_URL, "GET", "/logs/verify")), 200


@app.get("/admin.php/users")
@access(ADMIN)
def admin_users():
    return jsonify(admin_call("/internal/admin/users/list")), 200


@app.post("/admin.php/users")
@access(ADMIN)
def admin_users_create():
    d = body()
    fields = {k: d.get(k) for k in ("fiscal_id", "name", "email", "role", "password")}
    return jsonify(admin_call("/internal/admin/users/create", fields)), 201


@app.patch("/admin.php/users/<fiscal_id>")
@access(ADMIN)
def admin_users_update(fiscal_id: str):
    d = body()
    fields = {k: d.get(k) for k in ("name", "email", "role", "unlock")}
    return jsonify(admin_call("/internal/admin/users/update", {"fiscal_id": fiscal_id, **fields})), 200


@app.post("/admin.php/users/<fiscal_id>/password")
@access(ADMIN)
def admin_users_password(fiscal_id: str):
    return jsonify(admin_call("/internal/admin/users/password",
                              {"fiscal_id": fiscal_id, "new_password": body().get("new_password")})), 200


@app.delete("/admin.php/users/<fiscal_id>")
@access(ADMIN)
def admin_users_delete(fiscal_id: str):
    return jsonify(admin_call("/internal/admin/users/delete", {"fiscal_id": fiscal_id})), 200


PAGE_FIELDS = ("label", "description", "content", "roles", "visible")


@app.get("/admin.php/pages")
@access(ADMIN)
def admin_pages():
    return jsonify(admin_call("/internal/admin/pages/list")), 200


@app.post("/admin.php/pages")
@access(ADMIN)
def admin_pages_create():
    d = body()
    fields = {k: d.get(k) for k in PAGE_FIELDS}
    return jsonify(admin_call("/internal/admin/pages/save", {"slug": d.get("slug"), "create": True, **fields})), 201


@app.put("/admin.php/pages/<slug>")
@access(ADMIN)
def admin_pages_update(slug: str):
    d = body()
    fields = {k: d.get(k) for k in PAGE_FIELDS}
    return jsonify(admin_call("/internal/admin/pages/save", {"slug": slug, "create": False, **fields})), 200


@app.delete("/admin.php/pages/<slug>")
@access(ADMIN)
def admin_pages_delete(slug: str):
    return jsonify(admin_call("/internal/admin/pages/delete", {"slug": slug})), 200


@app.get("/endpoints")
@access(SESSION)
def endpoints():
    """Liste des endpoints exposés (sans information sensible) — utile
    pour la documentation et la recette."""
    rules = sorted({(r.rule, ",".join(sorted(m for m in r.methods if m not in ("HEAD", "OPTIONS"))),
                     ACCESS.get(r.endpoint, "refusé")) for r in app.url_map.iter_rules() if r.endpoint != "static"})
    return jsonify([{"path": p, "methods": m, "access": a} for p, m, a in rules]), 200


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "webapp"}), 200


def _check_whitelist_complete() -> None:
    missing = [r.endpoint for r in app.url_map.iter_rules()
               if r.endpoint not in ACCESS and r.endpoint not in ("static", "health")]
    if missing:
        raise RuntimeError(f"Routes sans niveau d'accès déclaré : {missing}")


_check_whitelist_complete()

if __name__ == "__main__":
    internal.run_dev_server(app, 5000)
