"""
Envoi des événements vers le Collecteur de logs (« Puits de logs »).

Flux 12 : événements d'authentification, 2FA, RBAC — priorité normale.
Flux 13 : événements liés à l'échange de token administrateur —
priorité élevée, pour permettre leur priorisation côté collecteur.
"""
import os

import requests

LOG_COLLECTOR_URL = os.environ.get("LOG_COLLECTOR_URL", "http://localhost:5002")
SHARED_SECRET = os.environ.get("INTERNAL_SHARED_SECRET", "dev-internal-secret")


def send_log(account: str, action: str, endpoint: str, ip: str, priority: str = "normal",
             source: str = "auth-system") -> None:
    try:
        requests.post(
            f"{LOG_COLLECTOR_URL}/logs",
            json={
                "source": source,
                "account": account,
                "action": action,
                "endpoint": endpoint,
                "ip": ip,
                "priority": priority,
            },
            headers={"X-Internal-Secret": SHARED_SECRET},
            timeout=2,
        )
    except requests.RequestException:
        # Le collecteur de logs est temporairement injoignable : on ne
        # bloque jamais le flux d'authentification pour autant, mais en
        # production ceci mériterait une file de secours (retry/outbox).
        pass
