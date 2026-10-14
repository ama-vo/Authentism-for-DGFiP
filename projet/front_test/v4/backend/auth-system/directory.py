"""
Accès à l'annuaire LDAP — nœuds « Système d'authentification (LDAP) » et
« Modèle RBAC (LDAP) » du schéma.

Arborescence :
    dc=dgfip,dc=fr
    ├── ou=users    uid=<numéro fiscal>  (inetOrgPerson : cn, sn, mail, userPassword)
    └── ou=groups   cn=externes | cn=agents | cn=admins  (groupOfNames)

Le rôle d'un compte est déterminé UNIQUEMENT par son appartenance à
un groupe LDAP (RBAC), jamais par un champ libre.

Deux modes :
- LDAP_MODE=real (Docker) : vrai serveur OpenLDAP, en LDAPS avec
  vérification du certificat contre l'AC interne. Le mot de passe est
  vérifié par un *bind* LDAP en tant que l'utilisateur : c'est le
  serveur LDAP qui compare, le service ne lit jamais les empreintes.
- LDAP_MODE=mock (dev local / tests) : annuaire simulé en mémoire
  (ldap3 MOCK_SYNC), mono-processus.

Les mots de passe sont stockés au format {CRYPT}$6$ (SHA-512 crypt,
salé, 200 000 itérations par défaut), compris nativement par OpenLDAP.
"""
import os
import secrets
import ssl
import threading
from contextlib import contextmanager
from dataclasses import dataclass

from ldap3 import (BASE, MOCK_SYNC, MODIFY_ADD, MODIFY_DELETE, MODIFY_REPLACE, SUBTREE,
                   Connection, Server, Tls)
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars
from passlib.hash import sha512_crypt

from common.validation import ROLES, is_fiscal_id

BASE_DN = os.environ.get("LDAP_BASE_DN", "dc=dgfip,dc=fr")
USERS_OU = f"ou=users,{BASE_DN}"
GROUPS_OU = f"ou=groups,{BASE_DN}"
SERVICE_DN = os.environ.get("LDAP_BIND_DN", f"cn=admin,{BASE_DN}")
SERVICE_PASSWORD = os.environ.get("LDAP_BIND_PASSWORD", "dev-ldap-password")
HASH_ROUNDS = int(os.environ.get("PASSWORD_HASH_ROUNDS", "200000"))

ROLE_GROUPS = {
    "external": f"cn=externes,{GROUPS_OU}",
    "agent": f"cn=agents,{GROUPS_OU}",
    "admin": f"cn=admins,{GROUPS_OU}",
}
GROUP_ROLES = {dn.lower(): role for role, dn in ROLE_GROUPS.items()}

# Comptes de démonstration créés au premier démarrage si l'annuaire est
# vide (SEED_DEMO_ACCOUNTS=true). Mêmes identités que les versions v1-v3.
DEMO_ACCOUNTS = [
    {"fiscal_id": "1032005849213", "name": "Camille Dubreuil", "role": "agent",
     "email": "camille.dubreuil@dgfip.example", "password": "Agent!DGFiP2026"},
    {"fiscal_id": "2098741562034", "name": "Yanis Belkacem", "role": "external",
     "email": "yanis.belkacem@example.org", "password": "Usager!Externe26"},
    {"fiscal_id": "3011008876521", "name": "Sophie Mercier", "role": "admin",
     "email": "sophie.mercier@dgfip.example", "password": "Admin!SysDGFiP26"},
]


class DirectoryError(Exception):
    """Annuaire injoignable ou opération refusée par le serveur."""


@dataclass
class LdapUser:
    dn: str
    fiscal_id: str
    name: str
    email: str


def hash_password(password: str) -> str:
    return "{CRYPT}" + sha512_crypt.using(rounds=HASH_ROUNDS).hash(password)


def _verify_hash(stored: str, password: str) -> bool:
    if not stored.startswith("{CRYPT}"):
        return False
    try:
        return sha512_crypt.verify(password, stored[len("{CRYPT}"):])
    except ValueError:
        return False


# Empreinte factice : vérifiée quand le compte n'existe pas, pour que le
# temps de réponse ne révèle pas l'existence d'un numéro fiscal.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def user_dn(fiscal_id: str) -> str:
    if not is_fiscal_id(fiscal_id):
        # Le numéro fiscal entre dans un DN : on n'accepte que 13 chiffres.
        raise DirectoryError("Numéro fiscal invalide.")
    return f"uid={fiscal_id},{USERS_OU}"


def _first(entry, attr: str) -> str:
    value = entry.get(attr) if isinstance(entry, dict) else None
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    return "" if value is None else str(value)


class Directory:
    def __init__(self):
        self.mode = os.environ.get("LDAP_MODE", "mock")
        self._lock = threading.Lock()
        if self.mode == "mock":
            self._server = Server("mock-dgfip-ldap")
            self._mock = Connection(self._server, user=SERVICE_DN, password=SERVICE_PASSWORD,
                                    client_strategy=MOCK_SYNC)
            self._mock.strategy.add_entry(SERVICE_DN, {"objectClass": ["person"], "cn": "admin", "sn": "admin",
                                                       "userPassword": SERVICE_PASSWORD})
            self._mock.strategy.add_entry(BASE_DN, {"objectClass": ["domain"]})
            self._mock.bind()
        else:
            url = os.environ.get("LDAP_URL", "ldaps://ldap:636")
            ca_file = os.environ.get("LDAP_CA_FILE") or os.environ.get("TLS_CA")
            tls = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=ca_file, version=ssl.PROTOCOL_TLS_CLIENT) \
                if ca_file else None
            self._server = Server(url, use_ssl=url.startswith("ldaps://"), tls=tls, connect_timeout=5)

    # -- connexions -----------------------------------------------------
    @contextmanager
    def _conn(self):
        if self.mode == "mock":
            with self._lock:
                yield self._mock
            return
        try:
            conn = Connection(self._server, user=SERVICE_DN, password=SERVICE_PASSWORD,
                              auto_bind=True, receive_timeout=10, raise_exceptions=False)
        except LDAPException as exc:
            raise DirectoryError("Annuaire LDAP injoignable.") from exc
        try:
            yield conn
        finally:
            conn.unbind()

    @staticmethod
    def _check(conn, ok: bool, what: str) -> None:
        if not ok:
            raise DirectoryError(f"{what} : {conn.result.get('description', 'erreur LDAP')}")

    @staticmethod
    def _search(conn, base: str, flt: str, attrs: list[str], scope=SUBTREE) -> list[dict]:
        conn.search(base, flt, search_scope=scope, attributes=attrs)
        return [{"dn": e["dn"], **e.get("attributes", {})} for e in conn.response or [] if e.get("type", "searchResEntry") == "searchResEntry"]

    # -- initialisation -------------------------------------------------
    def ensure_structure(self, seed_demo: bool) -> None:
        """Idempotent : crée les OU, les groupes RBAC et (option) les
        comptes de démonstration s'ils n'existent pas encore."""
        with self._conn() as conn:
            for ou in (USERS_OU, GROUPS_OU):
                if not self._search(conn, ou, "(objectClass=*)", ["ou"], scope=BASE):
                    self._check(conn, conn.add(ou, ["organizationalUnit"], {"ou": ou.split(",")[0][3:]}), "Création OU")
            for role, group_dn in ROLE_GROUPS.items():
                if not self._search(conn, group_dn, "(objectClass=*)", ["cn"], scope=BASE):
                    # groupOfNames impose au moins un membre : le compte de
                    # service sert de membre « sentinelle », ignoré par le RBAC.
                    self._check(conn, conn.add(group_dn, ["groupOfNames"],
                                               {"cn": group_dn.split(",")[0][3:], "member": [SERVICE_DN]}),
                                "Création groupe")
        if seed_demo:
            for acc in DEMO_ACCOUNTS:
                if not self.find_user(acc["fiscal_id"]):
                    self.create_user(acc["fiscal_id"], acc["name"], acc["email"], acc["role"], acc["password"])

    # -- lecture --------------------------------------------------------
    def find_user(self, fiscal_id: str) -> LdapUser | None:
        if not is_fiscal_id(fiscal_id):
            return None
        with self._conn() as conn:
            rows = self._search(conn, USERS_OU, f"(&(objectClass=inetOrgPerson)(uid={escape_filter_chars(fiscal_id)}))",
                                ["cn", "mail"])
        if not rows:
            return None
        row = rows[0]
        return LdapUser(dn=row["dn"], fiscal_id=fiscal_id, name=_first(row, "cn"), email=_first(row, "mail"))

    def authenticate(self, fiscal_id: str, password: str) -> LdapUser | None:
        """Flux 2/3 : validation des identifiants contre le registre LDAP."""
        user = self.find_user(fiscal_id)
        if not user or not password:
            _verify_hash(_DUMMY_HASH, password or "x")
            return None
        if self.mode == "mock":
            with self._conn() as conn:
                rows = self._search(conn, user.dn, "(objectClass=*)", ["userPassword"], scope=BASE)
            stored = _first(rows[0], "userPassword") if rows else ""
            return user if _verify_hash(stored, password) else None
        try:
            conn = Connection(self._server, user=user.dn, password=password, receive_timeout=10,
                              raise_exceptions=False)
            ok = conn.bind()
            conn.unbind()
        except LDAPException as exc:
            raise DirectoryError("Annuaire LDAP injoignable.") from exc
        return user if ok else None

    def get_role(self, fiscal_id: str) -> str | None:
        """Flux 7/8 et 10 : rôle = groupe LDAP dont le compte est membre."""
        if not is_fiscal_id(fiscal_id):
            return None
        dn = user_dn(fiscal_id)
        with self._conn() as conn:
            rows = self._search(conn, GROUPS_OU, f"(&(objectClass=groupOfNames)(member={escape_filter_chars(dn)}))", ["cn"])
        roles = {GROUP_ROLES.get(r["dn"].lower()) for r in rows} - {None}
        # Si un compte se retrouvait dans plusieurs groupes, on retient
        # le rôle le MOINS privilégié (principe de moindre privilège).
        for role in ROLES:
            if role in roles:
                return role
        return None

    def is_admin(self, fiscal_id: str) -> bool:
        return self.get_role(fiscal_id) == "admin"

    def list_users(self) -> list[dict]:
        with self._conn() as conn:
            users = self._search(conn, USERS_OU, "(objectClass=inetOrgPerson)", ["uid", "cn", "mail"])
            groups = self._search(conn, GROUPS_OU, "(objectClass=groupOfNames)", ["member"])
        role_of: dict[str, str] = {}
        for g in groups:
            role = GROUP_ROLES.get(g["dn"].lower())
            members = g.get("member") or []
            for m in members if isinstance(members, list) else [members]:
                role_of.setdefault(str(m).lower(), role)
        result = [{
            "fiscal_id": _first(u, "uid"),
            "name": _first(u, "cn"),
            "email": _first(u, "mail"),
            "role": role_of.get(u["dn"].lower()),
        } for u in users]
        return sorted(result, key=lambda u: u["fiscal_id"])

    def count_role(self, role: str) -> int:
        return sum(1 for u in self.list_users() if u["role"] == role)

    # -- écriture (portail administrateur) -----------------------------
    def create_user(self, fiscal_id: str, name: str, email: str, role: str, password: str) -> None:
        dn = user_dn(fiscal_id)
        with self._conn() as conn:
            ok = conn.add(dn, ["inetOrgPerson"], {
                "uid": fiscal_id, "cn": name, "sn": name.split()[-1], "mail": email,
                "userPassword": hash_password(password),
            })
            self._check(conn, ok, "Création du compte")
            self._check(conn, conn.modify(ROLE_GROUPS[role], {"member": [(MODIFY_ADD, [dn])]}), "Attribution du rôle")

    def update_user(self, fiscal_id: str, name: str | None = None, email: str | None = None) -> None:
        changes = {}
        if name:
            changes["cn"] = [(MODIFY_REPLACE, [name])]
            changes["sn"] = [(MODIFY_REPLACE, [name.split()[-1]])]
        if email:
            changes["mail"] = [(MODIFY_REPLACE, [email])]
        if changes:
            with self._conn() as conn:
                self._check(conn, conn.modify(user_dn(fiscal_id), changes), "Modification du compte")

    def set_role(self, fiscal_id: str, role: str) -> None:
        dn = user_dn(fiscal_id)
        with self._conn() as conn:
            for r, group_dn in ROLE_GROUPS.items():
                rows = self._search(conn, group_dn, "(objectClass=groupOfNames)", ["member"], scope=BASE)
                members = [str(m).lower() for m in (rows[0].get("member") or [])] if rows else []
                if r == role and dn.lower() not in members:
                    self._check(conn, conn.modify(group_dn, {"member": [(MODIFY_ADD, [dn])]}), "Ajout au groupe")
                elif r != role and dn.lower() in members:
                    self._check(conn, conn.modify(group_dn, {"member": [(MODIFY_DELETE, [dn])]}), "Retrait du groupe")

    def set_password(self, fiscal_id: str, password: str) -> None:
        with self._conn() as conn:
            ok = conn.modify(user_dn(fiscal_id), {"userPassword": [(MODIFY_REPLACE, [hash_password(password)])]})
            self._check(conn, ok, "Changement de mot de passe")

    def delete_user(self, fiscal_id: str) -> None:
        dn = user_dn(fiscal_id)
        with self._conn() as conn:
            for group_dn in ROLE_GROUPS.values():
                rows = self._search(conn, group_dn, "(objectClass=groupOfNames)", ["member"], scope=BASE)
                members = [str(m).lower() for m in (rows[0].get("member") or [])] if rows else []
                if dn.lower() in members:
                    self._check(conn, conn.modify(group_dn, {"member": [(MODIFY_DELETE, [dn])]}), "Retrait du groupe")
            self._check(conn, conn.delete(dn), "Suppression du compte")


_directory: Directory | None = None


def get_directory() -> Directory:
    global _directory
    if _directory is None:
        _directory = Directory()
    return _directory
