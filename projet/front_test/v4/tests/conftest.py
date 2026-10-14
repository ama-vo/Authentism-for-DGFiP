"""
Tests d'intégration en processus : les trois services Flask tournent
dans le même interpréteur (annuaire LDAP simulé + Redis en mémoire) et
les appels inter-services sont routés vers leurs clients de test.
Lancement : depuis la racine du projet, `python -m pytest tests -q`.
"""
import os
import sys
import tempfile

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND = os.path.join(ROOT, "backend")
for sub in ("", "auth-system", "webapp", "log-collector"):
    sys.path.insert(0, os.path.join(BACKEND, sub))

LOG_FILE = os.path.join(tempfile.mkdtemp(), "events.jsonl")
os.environ.update({
    "LDAP_MODE": "mock",
    "REDIS_URL": "memory://",
    "PASSWORD_HASH_ROUNDS": "5000",
    "DEBUG_EXPOSE_MFA_CODE": "true",
    "COOKIE_SECURE": "false",
    "TRUST_PROXY": "true",
    "LOG_DB_PATH": LOG_FILE,
    "SMTP_HOST": "",
    "INTERNAL_SHARED_SECRETS": "test-secret-0123456789abcdef0123456789",
    "SERVICE_NAME": "tests",
})

from common import internal  # noqa: E402

import log_service  # noqa: E402
import auth_service  # noqa: E402
import store  # noqa: E402
import web_service  # noqa: E402

_clients = {
    web_service.AUTH_SYSTEM_URL: auth_service.app.test_client(),
    web_service.LOG_COLLECTOR_URL: log_service.app.test_client(),
}


def _fake_call(base_url, method, path, payload=None, params=None, timeout=5):
    client = _clients[base_url]
    res = client.open(path, method=method, json=payload, query_string=params,
                      headers={"X-Internal-Secret": internal.OUTGOING_SECRET})
    data = res.get_json(silent=True)
    data = {} if data is None else data
    if res.status_code >= 400:
        raise internal.ServiceError(data.get("error", "Erreur interne."), res.status_code, data)
    return data


internal.call = _fake_call

AGENT = ("1032005849213", "Agent!DGFiP2026")
EXTERNAL = ("2098741562034", "Usager!Externe26")
ADMIN = ("3011008876521", "Admin!SysDGFiP26")
HDR = {"X-Requested-With": "fetch", "X-Real-IP": "203.0.113.7"}


@pytest.fixture(autouse=True)
def _reset_state():
    # Remet à zéro compteurs, verrous et sessions entre deux tests (les
    # comptes LDAP et les pages sont conservés).
    for key in store.r.scan_iter("rl:*"):
        store.r.delete(key)
    for key in store.r.scan_iter("lock:*"):
        store.r.delete(key)
    yield


@pytest.fixture
def web():
    return web_service.app.test_client()


def login(client, account):
    fiscal_id, password = account
    res = client.post("/login.php", json={"fiscal_id": fiscal_id, "password": password}, headers=HDR)
    assert res.status_code == 200, res.get_json()
    data = res.get_json()
    res = client.post("/login.php/verify", json={"challenge_token": data["challenge_token"],
                                                  "code": data["debug_code"]}, headers=HDR)
    assert res.status_code == 200, res.get_json()
    return res.get_json()


def admin_login(client, account=ADMIN):
    login(client, account)
    res = client.post("/admin.php/token", json={"password": account[1]}, headers=HDR)
    assert res.status_code == 200, res.get_json()
    return client
