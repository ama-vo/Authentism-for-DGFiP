"""
État serveur du Système d'authentification, stocké dans Redis.

Redis est partagé par tous les workers et toutes les instances
d'auth-system : on peut donc monter en charge horizontalement
(cahier des charges §3.1) sans perdre les sessions.

Les jetons ne sont JAMAIS stockés en clair : la clé Redis est
l'empreinte SHA-256 du jeton. Une fuite du contenu de Redis ne permet
donc pas de réutiliser une session. Les codes MFA sont stockés sous
forme de HMAC.

REDIS_URL=memory:// utilise une implémentation en mémoire (fakeredis)
pour le développement local et les tests.
"""
import hashlib
import hmac
import json
import os
import secrets
import time

MFA_CODE_TTL = int(os.environ.get("MFA_CODE_TTL_SECONDS", "300"))
MFA_MAX_ATTEMPTS = 3
MFA_MAX_RESENDS = 3
SESSION_IDLE_TTL = int(os.environ.get("SESSION_IDLE_TTL_SECONDS", "900"))
SESSION_MAX_AGE = int(os.environ.get("SESSION_MAX_AGE_SECONDS", str(8 * 3600)))
ADMIN_SESSION_TTL = int(os.environ.get("ADMIN_SESSION_TTL_SECONDS", "600"))


def _make_redis():
    url = os.environ.get("REDIS_URL", "memory://")
    if url.startswith("memory://"):
        import fakeredis
        return fakeredis.FakeRedis(decode_responses=True)
    import redis
    ca = os.environ.get("REDIS_CA_FILE")
    kwargs = {"ssl_ca_certs": ca} if ca and url.startswith("rediss://") else {}
    return redis.Redis.from_url(url, decode_responses=True, socket_timeout=3, socket_connect_timeout=3, **kwargs)


r = _make_redis()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _code_hmac(token: str, code: str) -> str:
    return hmac.new(token.encode(), code.encode(), hashlib.sha256).hexdigest()


def mint_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


# ---------------------------------------------------------------------
# Challenges MFA (connexion) et réinitialisation de mot de passe
# ---------------------------------------------------------------------
def create_challenge(fiscal_id: str, purpose: str, code: str) -> str:
    token = secrets.token_urlsafe(32)
    key = f"chal:{token_hash(token)}"
    r.hset(key, mapping={"fiscal_id": fiscal_id, "purpose": purpose,
                         "code": _code_hmac(token, code), "attempts": 0, "resends": 0})
    r.expire(key, MFA_CODE_TTL)
    return token


def get_challenge(token: str, purpose: str) -> dict | None:
    data = r.hgetall(f"chal:{token_hash(token)}")
    if not data or data.get("purpose") != purpose:
        return None
    return data


def check_code(token: str, challenge: dict, code: str) -> bool:
    return hmac.compare_digest(challenge["code"], _code_hmac(token, code))


def register_failure(token: str) -> int:
    key = f"chal:{token_hash(token)}"
    attempts = r.hincrby(key, "attempts", 1)
    if attempts >= MFA_MAX_ATTEMPTS:
        r.delete(key)  # terminaison : il faut recommencer depuis le début
    return attempts


def replace_code(token: str, code: str) -> int | None:
    """Renvoie le nombre de renvois effectués, ou None si refusé."""
    key = f"chal:{token_hash(token)}"
    if not r.exists(key):
        return None
    resends = r.hincrby(key, "resends", 1)
    if resends > MFA_MAX_RESENDS:
        return None
    r.hset(key, mapping={"code": _code_hmac(token, code), "attempts": 0})
    r.expire(key, MFA_CODE_TTL)
    return resends


def consume_challenge(token: str) -> bool:
    """Suppression atomique : un challenge ne peut être utilisé qu'une
    fois, même en cas de requêtes concurrentes."""
    return r.delete(f"chal:{token_hash(token)}") == 1


# ---------------------------------------------------------------------
# Sessions (jeton de session normal + jeton administrateur scopé)
# ---------------------------------------------------------------------
def create_session(fiscal_id: str, role: str, name: str, scope: str = "normal",
                   parent: str | None = None, scoped_endpoint: str | None = None) -> str:
    token = secrets.token_urlsafe(32)
    h = token_hash(token)
    now = int(time.time())
    ttl = ADMIN_SESSION_TTL if scope == "admin" else SESSION_IDLE_TTL
    max_age = ADMIN_SESSION_TTL if scope == "admin" else SESSION_MAX_AGE
    key = f"sess:{h}"
    r.hset(key, mapping={
        "fiscal_id": fiscal_id, "role": role, "name": name, "scope": scope,
        "parent": parent or "", "scoped_endpoint": scoped_endpoint or "",
        "created": now, "absolute_expiry": now + max_age,
    })
    r.expire(key, ttl)
    r.sadd(f"usess:{fiscal_id}", h)
    r.expire(f"usess:{fiscal_id}", SESSION_MAX_AGE)
    return token


def get_session(token: str, scope: str = "normal") -> dict | None:
    if not token:
        return None
    h = token_hash(token)
    key = f"sess:{h}"
    data = r.hgetall(key)
    if not data or data.get("scope") != scope:
        return None
    if int(data.get("absolute_expiry", 0)) < time.time():
        revoke_hash(h, data.get("fiscal_id"))
        return None
    if scope == "admin":
        # Le jeton admin n'est valable que tant que la session normale
        # dont il est issu existe encore (déconnexion = perte des droits admin).
        if not r.exists(f"sess:{data.get('parent')}"):
            revoke_hash(h, data.get("fiscal_id"))
            return None
    else:
        # Renouvellement glissant : chaque activité repousse l'expiration
        # d'inactivité, dans la limite de la durée de vie absolue.
        remaining = int(data["absolute_expiry"]) - int(time.time())
        r.expire(key, max(1, min(SESSION_IDLE_TTL, remaining)))
    data["hash"] = h
    data["expires_in"] = r.ttl(key)
    return data


def revoke_hash(h: str, fiscal_id: str | None = None) -> None:
    r.delete(f"sess:{h}")
    if fiscal_id:
        r.srem(f"usess:{fiscal_id}", h)


def revoke_session(token: str) -> dict | None:
    h = token_hash(token)
    data = r.hgetall(f"sess:{h}")
    revoke_hash(h, data.get("fiscal_id") if data else None)
    return data or None


def revoke_all(fiscal_id: str) -> int:
    """Révocation de toutes les sessions d'un compte (changement de mot
    de passe, de rôle, suppression)."""
    hashes = r.smembers(f"usess:{fiscal_id}")
    for h in hashes:
        r.delete(f"sess:{h}")
    r.delete(f"usess:{fiscal_id}")
    return len(hashes)


def count_sessions(fiscal_id: str) -> int:
    return sum(1 for h in r.smembers(f"usess:{fiscal_id}") if r.exists(f"sess:{h}"))


# ---------------------------------------------------------------------
# Limitation de débit et verrouillage de compte (anti brute-force)
# ---------------------------------------------------------------------
def hit(key: str, window: int) -> int:
    k = f"rl:{key}"
    n = r.incr(k)
    if n == 1:
        r.expire(k, window)
    return n


def count(key: str) -> int:
    return int(r.get(f"rl:{key}") or 0)


def reset_counter(key: str) -> None:
    r.delete(f"rl:{key}")


def lock_account(fiscal_id: str, seconds: int) -> None:
    r.set(f"lock:{fiscal_id}", 1, ex=seconds)


def lock_remaining(fiscal_id: str) -> int:
    ttl = r.ttl(f"lock:{fiscal_id}")
    return ttl if ttl and ttl > 0 else 0


def unlock_account(fiscal_id: str) -> None:
    r.delete(f"lock:{fiscal_id}")
    reset_counter(f"fail:{fiscal_id}")


# ---------------------------------------------------------------------
# Registre des pages du tableau de bord (whitelist dynamique, modifiable
# par l'administrateur — Modèle RBAC : « Modifier les pages disponibles
# sur le dashboard »)
# ---------------------------------------------------------------------
DEFAULT_PAGES = [
    {"slug": "page1", "label": "Espace particulier", "visible": True, "roles": ["admin", "agent", "external"],
     "description": "Consultation de vos déclarations et avis d'imposition.",
     "content": "Bienvenue dans votre espace particulier. Vos derniers avis d'imposition et déclarations apparaîtront ici."},
    {"slug": "outils-agents", "label": "Outils agents", "visible": True, "roles": ["admin", "agent"],
     "description": "Applications métier réservées aux agents de la DGFiP.",
     "content": "Accès aux applications métier internes : gestion des dossiers, recherche de contribuables, suivi des réclamations."},
]


def seed_pages() -> None:
    for page in DEFAULT_PAGES:
        r.hsetnx("pages", page["slug"], json.dumps(page, ensure_ascii=False))


def list_pages() -> list[dict]:
    pages = [json.loads(v) for v in r.hgetall("pages").values()]
    return sorted(pages, key=lambda p: p["slug"])


def get_page(slug: str) -> dict | None:
    raw = r.hget("pages", slug)
    return json.loads(raw) if raw else None


def save_page(page: dict) -> None:
    r.hset("pages", page["slug"], json.dumps(page, ensure_ascii=False))


def delete_page(slug: str) -> bool:
    return r.hdel("pages", slug) == 1


def ping() -> bool:
    try:
        return bool(r.ping())
    except Exception:  # noqa: BLE001
        return False
