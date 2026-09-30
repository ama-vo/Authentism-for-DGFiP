from flask import Blueprint, g, jsonify

from security import log_event, require_session

bp = Blueprint("services", __name__, url_prefix="/api/services")

# Liste d'autorisation (whitelist) par rôle — §2.5 du cahier des charges.
# Toute ressource absente de cette liste, ou tout rôle non listé pour une
# ressource donnée, se voit refuser l'accès et l'événement est journalisé.
SERVICE_WHITELIST = {
    "particulier": {"agent", "admin"},
    "professionnel": {"agent", "admin"},
    "cadastre": {"agent", "admin"},
    "messagerie": {"agent", "external", "admin"},
    "mon-compte": {"agent", "external", "admin"},
}

SERVICE_LABELS = {
    "particulier": "Espace particulier",
    "professionnel": "Espace professionnel",
    "cadastre": "Cadastre",
    "messagerie": "Messagerie sécurisée",
    "mon-compte": "Mon compte",
}


@bp.get("")
@require_session(scope="normal")
def list_services():
    role = g.user.role
    return jsonify([
        {
            "id": service_id,
            "name": SERVICE_LABELS[service_id],
            "allowed": role in allowed_roles,
        }
        for service_id, allowed_roles in SERVICE_WHITELIST.items()
    ]), 200


@bp.post("/<service_id>/access")
@require_session(scope="normal")
def access_service(service_id):
    allowed_roles = SERVICE_WHITELIST.get(service_id)
    endpoint = f"/api/services/{service_id}/access"

    if allowed_roles is None:
        log_event(g.user.fiscal_id, "Accès refusé (endpoint inconnu)", endpoint, "high")
        return jsonify({"error": "Ressource inconnue."}), 404

    if g.user.role not in allowed_roles:
        log_event(g.user.fiscal_id, "Accès refusé (hors liste d'autorisation)", endpoint, "high")
        return jsonify({"error": "Accès refusé pour votre rôle."}), 403

    log_event(g.user.fiscal_id, f"Accès au service « {SERVICE_LABELS[service_id]} »", endpoint, "normal")
    return jsonify({"ok": True, "service": SERVICE_LABELS[service_id]}), 200
