import os

import requests

AUTH_SYSTEM_URL = os.environ.get("AUTH_SYSTEM_URL", "http://localhost:5001")
LOG_COLLECTOR_URL = os.environ.get("LOG_COLLECTOR_URL", "http://localhost:5002")
SHARED_SECRET = os.environ.get("INTERNAL_SHARED_SECRET", "dev-internal-secret")


class AuthSystemError(Exception):
    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.message = message
        self.status = status


def _call(path: str, payload: dict) -> dict:
    try:
        res = requests.post(
            f"{AUTH_SYSTEM_URL}{path}",
            json=payload,
            headers={"X-Internal-Secret": SHARED_SECRET},
            timeout=5,
        )
    except requests.RequestException as exc:
        raise AuthSystemError("Système d'authentification injoignable.", 503) from exc

    data = res.json() if res.content else {}
    if res.status_code >= 400:
        raise AuthSystemError(data.get("error", "Erreur d'authentification."), res.status_code)
    return data


def check_credentials(fiscal_id: str, password: str, ip: str) -> dict:
    return _call("/internal/auth/credentials", {"fiscal_id": fiscal_id, "password": password, "ip": ip})


def verify_2fa(pending_token: str, code: str, ip: str) -> dict:
    return _call("/internal/auth/2fa/verify", {"pending_token": pending_token, "code": code, "ip": ip})


def resend_2fa(pending_token: str) -> dict:
    return _call("/internal/auth/2fa/resend", {"pending_token": pending_token})


def rbac_check(token: str, page: str, ip: str) -> dict:
    return _call("/internal/auth/rbac/check", {"token": token, "page": page, "ip": ip})


def admin_exchange(token: str, ip: str) -> dict:
    return _call("/internal/auth/admin/exchange", {"token": token, "ip": ip})


def session_check(token: str, scope: str = "normal", endpoint: str | None = None) -> dict:
    return _call("/internal/auth/session/check", {"token": token, "scope": scope, "endpoint": endpoint})


def logout(token: str, ip: str) -> dict:
    return _call("/internal/auth/logout", {"token": token, "ip": ip})


def fetch_logs(limit: int = 100) -> list:
    """Lecture du puits de logs, appelée uniquement par le handler
    /admin.php/logs — lui-même protégé par un jeton administrateur
    scopé. Le navigateur ne parle jamais directement au collecteur."""
    try:
        res = requests.get(
            f"{LOG_COLLECTOR_URL}/logs",
            params={"limit": limit},
            headers={"X-Internal-Secret": SHARED_SECRET},
            timeout=5,
        )
    except requests.RequestException as exc:
        raise AuthSystemError("Collecteur de logs injoignable.", 503) from exc

    if res.status_code >= 400:
        raise AuthSystemError("Lecture du journal refusée.", res.status_code)
    return res.json()
