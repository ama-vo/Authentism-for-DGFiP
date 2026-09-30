"""
État détenu par le Système d'authentification : c'est lui la source de
vérité des sessions (le nœud « Application Web » ne fait que relayer un
jeton opaque au navigateur, il ne le comprend ni ne le stocke).
"""
import secrets
import threading
import time
from dataclasses import dataclass, field

MFA_CODE_TTL_SECONDS = 300
MFA_MAX_ATTEMPTS = 3
NORMAL_SESSION_TTL_SECONDS = 2 * 60 * 60
ADMIN_SESSION_TTL_SECONDS = 10 * 60


@dataclass
class PendingMfa:
    fiscal_id: str
    code: str
    attempts: int = 0
    created_at: float = field(default_factory=time.time)

    def expired(self) -> bool:
        return time.time() - self.created_at > MFA_CODE_TTL_SECONDS


@dataclass
class Session:
    fiscal_id: str
    role: str
    scope: str  # "normal" ou "admin"
    # Pour un jeton "admin", scoped_endpoint restreint son usage à ce
    # seul endpoint (flux 11 : "token administrateur scopé ne
    # permettant que l'accès à /admin.php").
    scoped_endpoint: str | None = None
    created_at: float = field(default_factory=time.time)

    def expired(self) -> bool:
        ttl = ADMIN_SESSION_TTL_SECONDS if self.scope == "admin" else NORMAL_SESSION_TTL_SECONDS
        return time.time() - self.created_at > ttl


class Store:
    """Stockage en mémoire, protégé par un verrou — suffisant pour ce
    prototype pédagogique. En production : Redis ou équivalent partagé
    entre les instances du Système d'authentification."""

    def __init__(self):
        self._lock = threading.Lock()
        self._pending: dict[str, PendingMfa] = {}
        self._sessions: dict[str, Session] = {}

    def new_pending_mfa(self, fiscal_id: str, code: str) -> str:
        token = secrets.token_urlsafe(24)
        with self._lock:
            self._pending[token] = PendingMfa(fiscal_id=fiscal_id, code=code)
        return token

    def get_pending_mfa(self, token: str) -> PendingMfa | None:
        with self._lock:
            pending = self._pending.get(token)
            if pending and pending.expired():
                del self._pending[token]
                return None
            return pending

    def replace_pending_code(self, token: str, code: str) -> bool:
        with self._lock:
            pending = self._pending.get(token)
            if not pending:
                return False
            pending.code = code
            pending.attempts = 0
            pending.created_at = time.time()
            return True

    def register_mfa_failure(self, token: str) -> int:
        with self._lock:
            pending = self._pending.get(token)
            if not pending:
                return MFA_MAX_ATTEMPTS
            pending.attempts += 1
            attempts = pending.attempts
            if attempts >= MFA_MAX_ATTEMPTS:
                del self._pending[token]
            return attempts

    def consume_pending_mfa(self, token: str) -> None:
        with self._lock:
            self._pending.pop(token, None)

    def new_session(self, fiscal_id: str, role: str, scope: str = "normal",
                     scoped_endpoint: str | None = None) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sessions[token] = Session(
                fiscal_id=fiscal_id, role=role, scope=scope, scoped_endpoint=scoped_endpoint
            )
        return token

    def get_session(self, token: str) -> Session | None:
        with self._lock:
            session = self._sessions.get(token)
            if session and session.expired():
                del self._sessions[token]
                return None
            return session

    def revoke_session(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(token, None)


store = Store()
