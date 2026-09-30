"""
Collecteur de logs — correspond à l'entité « Puits de logs » du schéma.

Reçoit les événements émis par le Système d'authentification (flux 12 :
authentification, 2FA, RBAC) et par le module d'échange de token
administrateur (flux 13 : événements de session admin, à prioriser).
Ne parle à aucun autre service — c'est un puits, pas une source.
"""
import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_cors import CORS

DB_PATH = os.environ.get("LOG_DB_PATH", os.path.join(os.path.dirname(__file__), "events.jsonl"))
SHARED_SECRET = os.environ.get("INTERNAL_SHARED_SECRET", "dev-internal-secret")

app = Flask(__name__)
CORS(app)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_internal_auth():
    """Seuls les services internes (Système d'authentification) peuvent
    écrire dans le puits de logs — un secret partagé simule ici
    l'authentification mutuelle entre services (mTLS en production)."""
    return request.headers.get("X-Internal-Secret") == SHARED_SECRET


@app.post("/logs")
def ingest_event():
    if not require_internal_auth():
        return jsonify({"error": "Service non autorisé à écrire dans le puits de logs."}), 403

    data = request.get_json(silent=True) or {}
    required = {"source", "account", "action", "endpoint", "ip", "priority"}
    missing = required - data.keys()
    if missing:
        return jsonify({"error": f"Champs manquants : {', '.join(sorted(missing))}"}), 400
    if data["priority"] not in ("normal", "high"):
        return jsonify({"error": "priority doit valoir 'normal' ou 'high'."}), 400

    event = {
        "timestamp": utcnow_iso(),
        "source": data["source"],       # ex. "auth-system", "admin-token-exchange"
        "account": data["account"],
        "action": data["action"],
        "endpoint": data["endpoint"],
        "ip": data["ip"],
        "priority": data["priority"],
    }
    with open(DB_PATH, "a", encoding="utf-8") as f:
        import json
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    return jsonify({"ok": True}), 201


@app.get("/logs")
def list_events():
    """Consultation (typiquement par le tableau de bord admin de l'appli
    web, via un appel interne — jamais directement depuis le
    navigateur). Les événements de priorité 'high' — sessions
    administrateur — sont remontés en premier, comme le prévoit le
    flux 13 du schéma."""
    if not require_internal_auth():
        return jsonify({"error": "Service non autorisé à lire le puits de logs."}), 403

    limit = min(int(request.args.get("limit", 200)), 1000)
    priority_filter = request.args.get("priority")

    events = []
    if os.path.exists(DB_PATH):
        import json
        with open(DB_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))

    if priority_filter:
        events = [e for e in events if e["priority"] == priority_filter]

    # Priorisation : les événements "high" (sessions admin) remontent
    # en tête, puis tri antéchronologique au sein de chaque priorité.
    events.sort(key=lambda e: (e["priority"] != "high", e["timestamp"]), reverse=False)
    high = [e for e in events if e["priority"] == "high"][::-1]
    normal = [e for e in events if e["priority"] == "normal"][::-1]
    ordered = (high + normal)[:limit]

    return jsonify(ordered), 200


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "log-collector"}), 200


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 5002)), debug=True)
