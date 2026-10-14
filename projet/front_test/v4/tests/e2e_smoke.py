"""
Recette de bout en bout contre la pile Docker réellement déployée :
HTTPS via Nginx, LDAP réel, Redis, codes 2FA lus dans la boîte Mailpit.

    docker compose up -d
    docker compose cp pki:/pki/ca.crt ./ca.crt
    python tests/e2e_smoke.py            (requiert le paquet `requests`)

Variables : BASE_URL (https://localhost), MAILPIT_URL (http://localhost:8025),
CA_FILE (./ca.crt).
"""
import calendar
import os
import re
import socket
import sys
import time
import uuid

import requests

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = os.environ.get("BASE_URL", "https://localhost")
MAILPIT = os.environ.get("MAILPIT_URL", "http://localhost:8025")
CA = os.environ.get("CA_FILE", os.path.join(ROOT, "ca.crt"))
HDR = {"X-Requested-With": "fetch"}

AGENT = ("1032005849213", "Agent!DGFiP2026", "camille.dubreuil@dgfip.example")
EXTERNAL = ("2098741562034", "Usager!Externe26", "yanis.belkacem@example.org")
ADMIN = ("3011008876521", "Admin!SysDGFiP26", "sophie.mercier@dgfip.example")

results: list[tuple[bool, str]] = []


def check(cond: bool, label: str) -> None:
    results.append((bool(cond), label))
    print(("  OK   " if cond else "  ÉCHEC ") + label)


def client() -> requests.Session:
    s = requests.Session()
    s.verify = CA
    s.headers.update(HDR)
    return s


def latest_code(email: str, after: float) -> str:
    """Lit le dernier code envoyé à `email` dans Mailpit (flux 4)."""
    for _ in range(40):
        res = requests.get(f"{MAILPIT}/api/v1/search", params={"query": f'to:"{email}"', "limit": 5}, timeout=5)
        for msg in res.json().get("messages", []):
            created = msg.get("Created", "")
            ts = calendar.timegm(time.strptime(created[:19], "%Y-%m-%dT%H:%M:%S")) if created else 0
            if ts >= after - 2:
                text = requests.get(f"{MAILPIT}/api/v1/message/{msg['ID']}", timeout=5).json()["Text"]
                match = re.search(r"\b(\d{6})\b", text)
                if match:
                    return match.group(1)
        time.sleep(0.25)
    raise RuntimeError(f"Aucun code reçu pour {email}")


def login(s: requests.Session, account) -> dict:
    fiscal_id, password, email = account
    t = time.time()
    r = s.post(f"{BASE}/api/login.php", json={"fiscal_id": fiscal_id, "password": password})
    assert r.status_code == 200, r.text
    challenge = r.json()
    code = latest_code(email, t)
    r = s.post(f"{BASE}/api/login.php/verify", json={"challenge_token": challenge["challenge_token"], "code": code})
    assert r.status_code == 200, r.text
    return {**r.json(), "challenge": challenge, "set_cookie": r.headers.get("Set-Cookie", "")}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # console Windows
    print(f"Recette sur {BASE}\n")

    print("[Transport et exposition]")
    r = requests.get(BASE.replace("https://", "http://"), allow_redirects=False, timeout=5)
    check(r.status_code == 301 and r.headers["Location"].startswith("https://"), "HTTP redirigé vers HTTPS")
    r = requests.get(BASE, verify=CA, timeout=5)
    check(r.status_code == 200, "Certificat HTTPS valide pour l'AC Authentism (PKI)")
    for h in ("Strict-Transport-Security", "Content-Security-Policy", "X-Frame-Options", "X-Content-Type-Options"):
        check(h in r.headers, f"En-tête de sécurité {h}")
    for port in (5000, 5001, 5002, 389, 636, 6379, 1025):
        with socket.socket() as sock:
            sock.settimeout(1)
            closed = sock.connect_ex(("127.0.0.1", port)) != 0
        check(closed, f"Port interne {port} non exposé sur l'hôte")
    check(requests.get(f"{BASE}/src/main.tsx", verify=CA, timeout=5).status_code == 404, "Sources TypeScript non servies")

    print("\n[Authentification + MFA par e-mail]")
    agent = client()
    info = login(agent, AGENT)
    check(info["role"] == "agent", "Agent connecté après code 2FA reçu par e-mail")
    cookie = info["set_cookie"]
    check("__Host-dgfip_session" in cookie and "HttpOnly" in cookie and "Secure" in cookie and "SameSite=Strict" in cookie,
          "Cookie de session __Host-, HttpOnly, Secure, SameSite=Strict")
    check(info["challenge"].get("sent_to", "").startswith("c***@"), "Adresse e-mail masquée dans la réponse")
    check("debug_code" not in info["challenge"], "Code 2FA absent de la réponse HTTP")
    r = client().post(f"{BASE}/api/login.php", json={"fiscal_id": AGENT[0], "password": "Mauvais!Mdp2026"})
    check(r.status_code == 401, "Mauvais mot de passe refusé (message générique)")
    r = requests.post(f"{BASE}/api/login.php", json={"fiscal_id": AGENT[0], "password": AGENT[1]}, verify=CA)
    check(r.status_code == 403, "Requête sans en-tête anti-CSRF refusée")
    r = client().post(f"{BASE}/api/login.php", json={"fiscal_id": "*)(uid=*", "password": "x"})
    check(r.status_code == 401, "Injection LDAP dans l'identifiant rejetée")

    print("\n[Tableau de bord et RBAC]")
    links = {link["slug"]: link["allowed"] for link in agent.get(f"{BASE}/api/dashboard.php").json()["links"]}
    check(links.get("page1") and links.get("outils-agents") and not links.get("admin"), "Dashboard agent : pages selon le rôle")
    check(agent.get(f"{BASE}/api/outils-agents.php").status_code == 200, "Agent → /outils-agents.php autorisé")
    check(agent.get(f"{BASE}/api/admin.php/users").status_code == 403, "Agent → administration refusée")
    check(agent.post(f"{BASE}/api/admin.php/token", json={"password": AGENT[1]}).status_code == 403,
          "Agent → échange de jeton admin refusé (hors groupe LDAP admins)")
    ext = client()
    login(ext, EXTERNAL)
    check(ext.get(f"{BASE}/api/page1.php").status_code == 200, "Usager externe → /page1.php autorisé")
    check(ext.get(f"{BASE}/api/outils-agents.php").status_code == 403, "Usager externe → /outils-agents.php refusé")
    check(ext.get(f"{BASE}/api/inconnue.php").status_code == 404, "Endpoint hors whitelist refusé")
    check(requests.get(f"{BASE}/api/dashboard.php", verify=CA).status_code == 401, "Dashboard sans session refusé")

    print("\n[Administration (jeton scopé)]")
    adm = client()
    login(adm, ADMIN)
    check(adm.get(f"{BASE}/api/admin.php").status_code == 403, "Session admin seule insuffisante pour /admin.php")
    check(adm.post(f"{BASE}/api/admin.php/token", json={"password": "Faux!MotDePasse1"}).status_code == 401,
          "Ré-authentification exigée pour le jeton admin")
    r = adm.post(f"{BASE}/api/admin.php/token", json={"password": ADMIN[1]})
    check(r.status_code == 200 and "__Host-dgfip_admin" in r.headers.get("Set-Cookie", ""), "Jeton admin délivré")
    check(adm.get(f"{BASE}/api/admin.php").status_code == 200, "Accès /admin.php avec jeton admin")

    new_id = "4" + str(uuid.uuid4().int)[:12]
    new_email = f"test.{new_id}@example.org"
    new = {"fiscal_id": new_id, "name": "Compte Recette", "email": new_email, "role": "external",
           "password": "Recette!Compte26"}
    check(adm.post(f"{BASE}/api/admin.php/users", json=new).status_code == 201, "Création de compte (LDAP)")
    u = client()
    login(u, (new_id, new["password"], new_email))
    check(u.get(f"{BASE}/api/outils-agents.php").status_code == 403, "Nouveau compte externe : pages agents refusées")
    check(adm.patch(f"{BASE}/api/admin.php/users/{new_id}", json={"role": "agent"}).status_code == 200,
          "Modification des accès (groupe LDAP)")
    check(u.get(f"{BASE}/api/dashboard.php").status_code == 401, "Sessions révoquées après changement de rôle")
    login(u, (new_id, new["password"], new_email))
    check(u.get(f"{BASE}/api/outils-agents.php").status_code == 200, "Nouveau rôle effectif après reconnexion")
    check(adm.post(f"{BASE}/api/admin.php/users/{new_id}/password", json={"new_password": "Autre!Secret2026"}).status_code == 200,
          "Modification du mot de passe d'un autre compte")
    check(adm.delete(f"{BASE}/api/admin.php/users/{new_id}").status_code == 200, "Suppression du compte")
    r = client().post(f"{BASE}/api/login.php", json={"fiscal_id": new_id, "password": "Autre!Secret2026"})
    check(r.status_code == 401, "Compte supprimé : connexion impossible")

    page = {"slug": "recette", "label": "Page de recette", "description": "Test", "content": "Contenu",
            "roles": ["admin"], "visible": True}
    check(adm.post(f"{BASE}/api/admin.php/pages", json=page).status_code == 201, "Ajout d'une page au tableau de bord")
    check(ext.get(f"{BASE}/api/recette.php").status_code == 403, "Page réservée admin refusée à l'externe")
    adm.put(f"{BASE}/api/admin.php/pages/recette", json={**page, "roles": ["external", "agent", "admin"]})
    check(ext.get(f"{BASE}/api/recette.php").status_code == 200, "Rôles de la page modifiés par l'admin")
    adm.delete(f"{BASE}/api/admin.php/pages/recette")

    print("\n[Réinitialisation de mot de passe]")
    t = time.time()
    r = client().post(f"{BASE}/api/password/forgot", json={"fiscal_id": EXTERNAL[0]})
    token = r.json()["challenge_token"]
    code = latest_code(EXTERNAL[2], t)
    s = client()
    r = s.post(f"{BASE}/api/password/reset", json={"challenge_token": token, "code": code, "new_password": "faible"})
    check(r.status_code == 400, "Politique de mot de passe appliquée côté serveur")
    r = s.post(f"{BASE}/api/password/reset", json={"challenge_token": token, "code": code, "new_password": "Temp!Usager2026"})
    check(r.status_code == 200, "Réinitialisation par code e-mail")
    check(ext.get(f"{BASE}/api/dashboard.php").status_code == 401, "Anciennes sessions révoquées après réinitialisation")
    login(s, (EXTERNAL[0], "Temp!Usager2026", EXTERNAL[2]))
    adm.post(f"{BASE}/api/admin.php/users/{EXTERNAL[0]}/password", json={"new_password": EXTERNAL[1]})

    print("\n[Traçabilité]")
    spoof = client()
    spoof.post(f"{BASE}/api/login.php", json={"fiscal_id": "5555555555555", "password": "Nimporte!Quoi26"},
               headers={"X-Real-IP": "6.6.6.6", "X-Forwarded-For": "6.6.6.6"})
    logs = adm.get(f"{BASE}/api/admin.php/logs", params={"order": "time", "limit": 500}).json()
    check(all({"timestamp", "account", "action", "endpoint", "ip"} <= e.keys() for e in logs), "Champs obligatoires présents")
    check(all(e["timestamp"].endswith("Z") for e in logs), "Horodatage universel (UTC)")
    check(not any(e["ip"] == "6.6.6.6" for e in logs), "IP non falsifiable par X-Real-IP / X-Forwarded-For")
    prio = adm.get(f"{BASE}/api/admin.php/logs", params={"limit": 5}).json()
    check(prio and prio[0]["priority"] == "critical", "Événements critiques remontés en tête (flux 13)")
    check(any("Suppression du compte" in e["action"] for e in logs), "Suppression de compte journalisée")
    check(any(e["outcome"] == "failure" and "refusé" in e["action"] for e in logs), "Refus d'accès journalisés")
    check(adm.get(f"{BASE}/api/admin.php/logs/verify").json().get("valid") is True, "Chaîne d'intégrité HMAC valide")

    print("\n[Verrouillage anti brute-force]")
    adm.patch(f"{BASE}/api/admin.php/users/{AGENT[0]}", json={"unlock": True})  # remet le compteur à zéro
    victim = client()
    statuses = [victim.post(f"{BASE}/api/login.php", json={"fiscal_id": AGENT[0], "password": f"Faux!Essai{i:04d}"}).status_code
                for i in range(5)]
    r = victim.post(f"{BASE}/api/login.php", json={"fiscal_id": AGENT[0], "password": AGENT[1]})
    check(statuses == [401] * 5 and r.status_code == 423, f"Compte verrouillé après 5 échecs ({statuses} puis {r.status_code})")
    adm.patch(f"{BASE}/api/admin.php/users/{AGENT[0]}", json={"unlock": True})
    login(client(), AGENT)
    check(True, "Déverrouillage par l'administrateur")

    failed = [label for ok, label in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} vérifications réussies.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
