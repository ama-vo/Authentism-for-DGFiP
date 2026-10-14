"""
Envoi des événements vers le Collecteur de logs (« Puits de logs »).

Chaque événement contient au minimum (cahier des charges §3.2) :
timestamp UTC (posé par le collecteur), compte, action, endpoint, IP.

Priorités :
- "normal"   : authentification, 2FA, RBAC, navigation (flux 12)
- "high"     : accès au panneau d'administration, échange de jeton
               admin, réinitialisation de son propre mot de passe,
               refus d'accès (flux 13)
- "critical" : création / suppression de compte, modification des
               droits ou du mot de passe d'un autre utilisateur,
               verrouillage de compte
"""
import logging
import os

from common import internal

LOG_COLLECTOR_URL = os.environ.get("LOG_COLLECTOR_URL", "http://127.0.0.1:5002")
SOURCE = os.environ.get("SERVICE_NAME", "unknown")

logger = logging.getLogger("logclient")


def send_log(account: str, action: str, endpoint: str, ip: str, priority: str = "normal",
             outcome: str = "success") -> None:
    event = {
        "source": SOURCE,
        "account": (account or "inconnu")[:64],
        "action": action[:300],
        "endpoint": endpoint[:200],
        "ip": (ip or "inconnu")[:64],
        "priority": priority,
        "outcome": outcome,
    }
    try:
        internal.call(LOG_COLLECTOR_URL, "POST", "/logs", event, timeout=2)
    except internal.ServiceError:
        # On ne bloque jamais le parcours utilisateur si le puits est
        # injoignable, mais l'événement n'est pas perdu : il part sur
        # la sortie standard du conteneur (collectée par Docker).
        logger.warning("LOG-FALLBACK %s", event)
