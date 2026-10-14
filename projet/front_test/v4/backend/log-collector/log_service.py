"""
Collecteur de logs — entité « Puits de logs » du schéma.

Reçoit les événements de l'Application Web et du Système
d'authentification (flux 12), et priorise ceux liés aux sessions
administrateur (flux 13). Ne contacte aucun autre service : c'est un
puits, pas une source.

Intégrité (PLAN-D-ACTION §6 « protéger les logs contre la
modification ») : chaque événement est chaîné au précédent par un
HMAC-SHA256 (clé LOG_SIGNING_KEY, connue du seul collecteur). Toute
modification, suppression ou insertion d'une ligne dans le fichier
casse la chaîne, ce que détecte GET /logs/verify.
"""
import hashlib
import hmac
import json
import os
import sys
import threading
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import Flask, jsonify, request  # noqa: E402

from common import internal  # noqa: E402
from common.validation import bounded_int  # noqa: E402

DB_PATH = os.environ.get("LOG_DB_PATH", os.path.join(os.path.dirname(__file__), "events.jsonl"))
SIGNING_KEY = (os.environ.get("LOG_SIGNING_KEY") or internal.OUTGOING_SECRET).encode()
PRIORITIES = ("critical", "high", "normal")
PRIORITY_RANK = {p: i for i, p in enumerate(PRIORITIES)}
GENESIS = "0" * 64

app = Flask(__name__)
internal.harden_json_app(app)
internal.assert_production_ready()

_lock = threading.Lock()
_state = {"seq": 0, "last_hash": GENESIS, "loaded": False}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _digest(prev_hash: str, event: dict) -> str:
    body = {k: v for k, v in event.items() if k != "hash"}
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hmac.new(SIGNING_KEY, (prev_hash + canonical).encode("utf-8"), hashlib.sha256).hexdigest()


def _read_events() -> list[dict]:
    if not os.path.exists(DB_PATH):
        return []
    events = []
    with open(DB_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    events.append({"_corrupted": line[:200]})
    return events


def _load_state() -> None:
    if _state["loaded"]:
        return
    events = [e for e in _read_events() if "_corrupted" not in e]
    if events:
        _state["seq"] = int(events[-1].get("seq", len(events)))
        _state["last_hash"] = events[-1].get("hash", GENESIS)
    _state["loaded"] = True


def _clean(value, max_len: int) -> str:
    # Les journaux ne doivent pas pouvoir être pollués (injection de
    # retours à la ligne, caractères de contrôle — « log forging »).
    text = str(value)[:max_len]
    return "".join(c if c.isprintable() else "?" for c in text)


@app.post("/logs")
@internal.internal_only
def ingest_event():
    data = request.get_json(silent=True) or {}
    required = {"source", "account", "action", "endpoint", "ip", "priority"}
    missing = required - data.keys()
    if missing:
        return jsonify({"error": f"Champs manquants : {', '.join(sorted(missing))}"}), 400
    if data["priority"] not in PRIORITIES:
        return jsonify({"error": "priority doit valoir normal, high ou critical."}), 400

    with _lock:
        _load_state()
        event = {
            "seq": _state["seq"] + 1,
            "timestamp": _utcnow_iso(),
            "source": _clean(data["source"], 32),
            "account": _clean(data["account"], 64),
            "action": _clean(data["action"], 300),
            "endpoint": _clean(data["endpoint"], 200),
            "ip": _clean(data["ip"], 64),
            "priority": data["priority"],
            "outcome": _clean(data.get("outcome", "success"), 16),
            "prev_hash": _state["last_hash"],
        }
        event["hash"] = _digest(_state["last_hash"], event)
        with open(DB_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        _state["seq"] = event["seq"]
        _state["last_hash"] = event["hash"]

    return jsonify({"ok": True, "seq": event["seq"]}), 201


@app.get("/logs")
@internal.internal_only
def list_events():
    """Consultation (par l'Application Web, pour le panneau admin).
    order=priority (défaut) : critical puis high puis normal, chacun
    du plus récent au plus ancien (flux 13). order=time : chronologie
    inverse pure."""
    limit = bounded_int(request.args.get("limit"), 200, 1, 1000)
    priority = request.args.get("priority")
    account = request.args.get("account")
    order = request.args.get("order", "priority")

    with _lock:
        events = [e for e in _read_events() if "_corrupted" not in e]

    if priority in PRIORITIES:
        events = [e for e in events if e.get("priority") == priority]
    if account:
        events = [e for e in events if e.get("account") == account]

    events.sort(key=lambda e: e.get("seq", 0), reverse=True)
    if order != "time":
        events.sort(key=lambda e: PRIORITY_RANK.get(e.get("priority"), 9))

    public = [{k: v for k, v in e.items() if k not in ("hash", "prev_hash")} for e in events[:limit]]
    return jsonify(public), 200


@app.get("/logs/verify")
@internal.internal_only
def verify_chain():
    with _lock:
        events = _read_events()
    prev = GENESIS
    for index, event in enumerate(events, start=1):
        if "_corrupted" in event or event.get("prev_hash") != prev or _digest(prev, event) != event.get("hash"):
            return jsonify({"valid": False, "count": len(events), "first_invalid_line": index}), 200
        prev = event["hash"]
    return jsonify({"valid": True, "count": len(events)}), 200


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "log-collector"}), 200


if __name__ == "__main__":
    internal.run_dev_server(app, 5002)
