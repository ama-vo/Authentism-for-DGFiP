"""
Couche d'accès à l'annuaire LDAP.

Par défaut, utilise un annuaire LDAP *simulé en mémoire* (ldap3,
stratégie MOCK_SYNC) afin que ce service tourne sans dépendance
d'infrastructure externe. Le schéma (ou=users, ou=groups, RBAC par
appartenance à un groupe) reproduit fidèlement ce qu'on trouverait sur
un vrai annuaire d'entreprise.

Pour brancher un VRAI serveur LDAP (OpenLDAP, Active Directory...) :
positionner LDAP_MODE=real et LDAP_HOST/LDAP_PORT/LDAP_BIND_DN/
LDAP_BIND_PASSWORD/LDAP_BASE_DN dans l'environnement — le reste du
code (recherche, vérification de mot de passe, appartenance aux
groupes) est strictement identique dans les deux modes, seule la
fabrique de connexion change (cf. `_connect_real`).
"""
import base64
import hashlib
import hmac
import os
from dataclasses import dataclass

from ldap3 import ALL, SUBTREE, Connection, MOCK_SYNC, Server

BASE_DN = os.environ.get("LDAP_BASE_DN", "dc=dgfip,dc=local")
USERS_OU = f"ou=users,{BASE_DN}"
GROUPS_OU = f"ou=groups,{BASE_DN}"
SERVICE_DN = os.environ.get("LDAP_BIND_DN", f"cn=auth-system,{BASE_DN}")
SERVICE_PASSWORD = os.environ.get("LDAP_BIND_PASSWORD", "service-account-password")

ROLE_GROUPS = {
    "external": f"cn=externes,{GROUPS_OU}",
    "agent": f"cn=agents,{GROUPS_OU}",
    "admin": f"cn=admins,{GROUPS_OU}",
}

# Comptes de démonstration — mêmes identités que le prototype front,
# pour pouvoir enchaîner les deux sans les reconfigurer.
DEMO_ACCOUNTS = [
    {"fiscal_id": "1032005849213", "name": "Camille Dubreuil", "role": "agent", "password": "Agent!DGFiP2026"},
    {"fiscal_id": "2098741562034", "name": "Yanis Belkacem", "role": "external", "password": "Usager!Externe26"},
    {"fiscal_id": "3011008876521", "name": "Sophie Mercier", "role": "admin", "password": "Admin!SysDGFiP26"},
]


# --------------------------------------------------------------------
# {SSHA} — hachage salé standard LDAP (RFC-compatible OpenLDAP/AD).
# On l'implémente nous-mêmes côté application : c'est le format que
# stockerait un vrai annuaire, et c'est ce qu'un client LDAP doit
# vérifier lorsqu'il n'utilise pas un bind direct en tant que
# l'utilisateur (cf. note sur le choix d'architecture ci-dessous).
# --------------------------------------------------------------------
def make_ssha(password: str) -> str:
    salt = os.urandom(8)
    digest = hashlib.sha1(password.encode("utf-8") + salt).digest()
    return "{SSHA}" + base64.b64encode(digest + salt).decode("ascii")


def verify_ssha(ssha_value: str, password: str) -> bool:
    if not ssha_value.startswith("{SSHA}"):
        return False
    raw = base64.b64decode(ssha_value[len("{SSHA}"):])
    digest, salt = raw[:20], raw[20:]
    candidate = hashlib.sha1(password.encode("utf-8") + salt).digest()
    return hmac.compare_digest(digest, candidate)


@dataclass
class LdapUser:
    dn: str
    fiscal_id: str
    name: str
    email: str


class Directory:
    """Point d'entrée unique vers l'annuaire, quel que soit le mode
    (simulé ou réel). Le Système d'authentification s'y connecte en
    tant que *compte de service* (SERVICE_DN) — jamais en tant que
    l'utilisateur final, dont on ne connaît que le mot de passe
    fourni à l'instant du login."""

    def __init__(self):
        self.mode = os.environ.get("LDAP_MODE", "mock")
        self.conn: Connection = self._connect_mock() if self.mode == "mock" else self._connect_real()

    # -- fabriques de connexion -----------------------------------
    def _connect_mock(self) -> Connection:
        server = Server("mock-dgfip-ldap")
        conn = Connection(
            server, user=SERVICE_DN, password=SERVICE_PASSWORD, client_strategy=MOCK_SYNC
        )
        conn.strategy.add_entry(SERVICE_DN, {"objectClass": "person", "userPassword": SERVICE_PASSWORD})
        conn.bind()
        self._seed(conn)
        return conn

    def _connect_real(self) -> Connection:  # pragma: no cover - nécessite un vrai LDAP
        server = Server(
            os.environ["LDAP_HOST"],
            port=int(os.environ.get("LDAP_PORT", 636)),
            use_ssl=os.environ.get("LDAP_USE_SSL", "true").lower() == "true",
            get_info=ALL,
        )
        conn = Connection(server, user=SERVICE_DN, password=SERVICE_PASSWORD, auto_bind=True)
        return conn

    def _seed(self, conn: Connection) -> None:
        conn.strategy.add_entry(BASE_DN, {"objectClass": "domain"})
        conn.strategy.add_entry(USERS_OU, {"objectClass": "organizationalUnit"})
        conn.strategy.add_entry(GROUPS_OU, {"objectClass": "organizationalUnit"})

        members_by_role = {"external": [], "agent": [], "admin": []}
        for acc in DEMO_ACCOUNTS:
            user_dn = f"uid={acc['fiscal_id']},{USERS_OU}"
            conn.strategy.add_entry(
                user_dn,
                {
                    "objectClass": ["inetOrgPerson"],
                    "uid": acc["fiscal_id"],
                    "cn": acc["name"],
                    "mail": f"{acc['fiscal_id']}@dgfip-demo.local",
                    "userPassword": make_ssha(acc["password"]),
                },
            )
            members_by_role[acc["role"]].append(user_dn)

        for role, group_dn in ROLE_GROUPS.items():
            conn.strategy.add_entry(
                group_dn,
                {"objectClass": "groupOfNames", "cn": role, "member": members_by_role[role] or [SERVICE_DN]},
            )

    # -- opérations métier ------------------------------------------
    def find_user(self, fiscal_id: str) -> LdapUser | None:
        self.conn.search(
            USERS_OU, f"(uid={fiscal_id})", search_scope=SUBTREE, attributes=["cn", "mail", "userPassword"]
        )
        if not self.conn.entries:
            return None
        entry = self.conn.entries[0]
        return LdapUser(
            dn=str(entry.entry_dn),
            fiscal_id=fiscal_id,
            name=str(entry.cn),
            email=str(entry.mail),
        )

    def check_credentials(self, fiscal_id: str, password: str) -> LdapUser | None:
        """Recherche l'utilisateur puis vérifie son mot de passe contre
        le hash {SSHA} stocké — flux 2/3 du schéma (« attente de
        validation des identifiants contre le registre LDAP »)."""
        self.conn.search(
            USERS_OU, f"(uid={fiscal_id})", search_scope=SUBTREE, attributes=["cn", "mail", "userPassword"]
        )
        if not self.conn.entries:
            return None
        entry = self.conn.entries[0]
        stored_hash = str(entry.userPassword)
        if not verify_ssha(stored_hash, password):
            return None
        return LdapUser(dn=str(entry.entry_dn), fiscal_id=fiscal_id, name=str(entry.cn), email=str(entry.mail))

    def get_role(self, fiscal_id: str) -> str | None:
        """RBAC — correspond au nœud « Modèle RBAC (LDAP) » : le rôle est
        déterminé par l'appartenance à un groupe LDAP, pas par un champ
        libre sur le compte."""
        user_dn = f"uid={fiscal_id},{USERS_OU}"
        for role, group_dn in ROLE_GROUPS.items():
            self.conn.search(group_dn, "(objectClass=groupOfNames)", attributes=["member"])
            if self.conn.entries:
                members = self.conn.entries[0].member.values
                if user_dn in members:
                    return role
        return None

    def is_admin(self, fiscal_id: str) -> bool:
        """Flux 10 : vérification de l'appartenance au groupe
        administrateur avant échange du token."""
        return self.get_role(fiscal_id) == "admin"


_directory: Directory | None = None


def get_directory() -> Directory:
    global _directory
    if _directory is None:
        _directory = Directory()
    return _directory
