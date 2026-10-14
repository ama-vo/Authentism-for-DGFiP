"""
Authentification et transport des appels inter-services.

- Chaque appel interne porte l'en-tête X-Internal-Secret. Plusieurs
  secrets peuvent être acceptés simultanément (INTERNAL_SHARED_SECRETS,
  séparés par des virgules) : on peut ainsi RENOUVELER le secret sans
  interruption (ajout du nouveau, redéploiement, retrait de l'ancien).
  Le premier de la liste est celui utilisé pour émettre.
- La comparaison se fait en temps constant (hmac.compare_digest).
- Si TLS_CA est défini, les appels sortants sont faits en HTTPS et le
  certificat du destinataire est vérifié contre l'AC interne (PKI).
"""
import functools
import hmac
import os

import requests
from flask import jsonify, request


def _load_secrets() -> list[str]:
    raw = os.environ.get("INTERNAL_SHARED_SECRETS") or os.environ.get("INTERNAL_SHARED_SECRET") or ""
    values = [s.strip() for s in raw.split(",") if s.strip()]
    if not values:
        # Valeur de développement uniquement — refusée en production
        # par la vérification de démarrage (cf. assert_production_ready).
        values = ["dev-internal-secret-change-me"]
    return values


SECRETS = _load_secrets()
OUTGOING_SECRET = SECRETS[0]
TLS_CA = os.environ.get("TLS_CA") or None


def assert_production_ready() -> None:
    if os.environ.get("APP_ENV", "dev") == "production":
        for s in SECRETS:
            if len(s) < 32 or s.startswith("dev-") or "change" in s:
                raise RuntimeError("INTERNAL_SHARED_SECRETS trop faible pour la production.")


def is_internal_caller() -> bool:
    provided = request.headers.get("X-Internal-Secret", "")
    return any(hmac.compare_digest(provided.encode(), s.encode()) for s in SECRETS)


def internal_only(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if not is_internal_caller():
            return jsonify({"error": "Appelant non autorisé."}), 403
        return view(*args, **kwargs)

    return wrapper


class ServiceError(Exception):
    def __init__(self, message: str, status: int, payload: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.payload = payload or {}


_session = requests.Session()


def call(base_url: str, method: str, path: str, payload: dict | None = None,
         params: dict | None = None, timeout: float = 5) -> dict | list:
    try:
        res = _session.request(
            method,
            f"{base_url}{path}",
            json=payload,
            params=params,
            headers={"X-Internal-Secret": OUTGOING_SECRET},
            timeout=timeout,
            verify=TLS_CA if TLS_CA else True,
        )
    except requests.RequestException as exc:
        raise ServiceError("Service interne injoignable.", 503) from exc

    try:
        data = res.json() if res.content else {}
    except ValueError:
        data = {}
    if res.status_code >= 400:
        message = data.get("error", "Erreur interne.") if isinstance(data, dict) else "Erreur interne."
        raise ServiceError(message, res.status_code, data if isinstance(data, dict) else {})
    return data


def run_dev_server(app, default_port: int) -> None:
    """Lancement direct `python xxx_service.py` (développement). En
    conteneur c'est gunicorn qui sert l'application, avec TLS."""
    cert, key = os.environ.get("TLS_CERT"), os.environ.get("TLS_KEY")
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", default_port)),
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true",
        ssl_context=(cert, key) if cert and key else None,
    )


def harden_json_app(app) -> None:
    """En-têtes de sécurité communs à toutes les réponses JSON, et
    limite de taille des corps de requête."""
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024
    app.config["JSON_SORT_KEYS"] = False

    @app.after_request
    def _headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Frame-Options"] = "DENY"
        return resp

    @app.errorhandler(404)
    def _not_found(_e):
        return jsonify({"error": "Ressource introuvable."}), 404

    @app.errorhandler(405)
    def _method(_e):
        return jsonify({"error": "Méthode non autorisée."}), 405

    @app.errorhandler(413)
    def _too_large(_e):
        return jsonify({"error": "Requête trop volumineuse."}), 413

    @app.errorhandler(500)
    def _internal(_e):
        return jsonify({"error": "Erreur interne."}), 500
