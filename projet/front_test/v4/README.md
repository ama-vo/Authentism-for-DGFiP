# Authentism pour la DGFiP — v4

Système d'authentification complet pour les services de la DGFiP (projet
pédagogique). Cette version reprend l'architecture distribuée de la v3
(`../v3/dgfip-auth-distribue`), en **corrige les bugs** et implémente
**l'ensemble du cahier des charges** ([`DESCRIPTION.MD`](../../../DESCRIPTION.MD) à la racine du dépôt) et du
**modèle RBAC** ([`Modèle RBAC à implémenter.pdf`](<../../../Modèle RBAC à implémenter.pdf>)), en suivant les 13
flux du schéma [`ArchiWebDistribuée.drawio.svg`](../../../ArchiWebDistribuée.drawio.svg).

## Démarrage rapide (Docker)

Toutes les commandes se lancent depuis ce dossier (`projet/front_test/v4`).

Prérequis : Docker Desktop (Compose v2) et Python 3 (uniquement pour
générer le `.env`).

```bash
python scripts/init_env.py        # crée .env avec des secrets aléatoires
docker compose up --build -d      # ~1 min au premier lancement
docker compose ps                 # tous les services "healthy", pki "Exited (0)"
```

| Quoi | Où |
| --- | --- |
| Portail | **https://localhost** (http://localhost redirige) |
| Boîte mail de démo (codes 2FA) | **http://localhost:8025** (Mailpit) |

Le certificat HTTPS est signé par l'AC interne du projet. Pour supprimer
l'avertissement du navigateur, importez-la comme autorité de confiance :

```bash
docker compose cp pki:/pki/ca.crt ./ca.crt   # puis importer ca.crt dans le navigateur / le système
```

### Comptes de démonstration

| Rôle | Numéro fiscal | Mot de passe |
| --- | --- | --- |
| Agent DGFiP | `1032005849213` | `Agent!DGFiP2026` |
| Utilisateur externe | `2098741562034` | `Usager!Externe26` |
| Administrateur système | `3011008876521` | `Admin!SysDGFiP26` |

Parcours : numéro fiscal + mot de passe → code à 6 chiffres reçu dans
Mailpit → tableau de bord → (admin) « Panneau d'administration » →
re-saisie du mot de passe → gestion des comptes, des pages et du journal.

Arrêt : `docker compose down` (ajouter `-v` pour effacer annuaire,
sessions, journaux et certificats).

## Architecture

```
navigateur ──HTTPS──▶ frontend : Nginx (TLS, file d'attente, limitation de débit, répartition de charge)
                        │  réseau "edge"                         ── HTTPS vérifié par l'AC interne ──
                        ▼
                     webapp ×N  « Application Web » : whitelist des endpoints, cookies, anti-CSRF
                        │  réseau "core" (internal : aucune sortie Internet)
          ┌─────────────┼───────────────────┐
          ▼             ▼                   ▼
   auth-system ×N   log-collector      « Système d'authentification » ──LDAPS──▶ OpenLDAP (identités, groupes RBAC)
   (Redis : sessions,  « Puits de logs »                                  ──SMTP STARTTLS──▶ Mailpit (codes 2FA)
    codes MFA)         (chaîne HMAC)
```

| Service | Rôle | Exposé ? |
| --- | --- | --- |
| `pki` | Génère l'AC racine et un certificat X.509 par service ; les renouvelle s'ils expirent dans < 30 jours (certificats de 90 jours). S'exécute puis s'arrête. | non |
| `frontend` | React + TypeScript compilé, servi par Nginx ; relaie `/api/*` vers `webapp` | **80/443** |
| `webapp` | Seul point d'entrée de l'API. Aucune logique d'authentification : délègue tout à `auth-system` | non |
| `auth-system` | Identifiants, MFA, sessions, RBAC, échange de jeton admin, gestion des comptes | non |
| `log-collector` | Journal centralisé, priorisé, infalsifiable | non |
| `ldap` | OpenLDAP : `ou=users` (comptes) et `ou=groups` (`externes`, `agents`, `admins`) | non |
| `redis` | Sessions, codes MFA, compteurs anti brute-force, registre des pages | non |
| `mailpit` | Serveur SMTP de test + webmail | 127.0.0.1:8025 |

### Correspondance flux du schéma → code

| Flux | Description | Code |
| --- | --- | --- |
| 1 | POST `/login.php` login/mot de passe | `webapp/web_service.py::login` |
| 2/3 | Validation contre LDAP (bind LDAPS en tant que l'utilisateur) | `auth-system/auth_service.py::login` → `directory.py::authenticate` |
| 4 | Code envoyé à l'e-mail du compte | `auth_service.py::login` → `mailer.py::send_code` |
| 5 | Validation du code 2FA ou terminaison (3 essais, 5 min, usage unique) | `auth_service.py::mfa_verify` |
| 6 | Redirection vers `/dashboard.php` | `web_service.py::login_verify` (+ cookie de session) |
| 7/8 | Rôle lu dans LDAP et confronté aux rôles autorisés de la page | `auth_service.py::rbac_check`, `dashboard` → `directory.py::get_role` |
| 9 | Accès à l'endpoint `/<page>.php` | `web_service.py::standard_page` |
| 10 | Vérification de l'appartenance au groupe LDAP `admins` | `auth_service.py::admin_exchange` → `directory.py::is_admin` |
| 11 | Échange contre un jeton admin scopé `/admin.php` (10 min, mot de passe redemandé) | `auth_service.py::admin_exchange`, `admin_required` |
| 12 | Centralisation des événements | `common/logclient.py::send_log` → `log-collector/log_service.py::ingest_event` |
| 13 | Priorisation des événements d'administration | priorités `critical` / `high` / `normal`, tri dans `log_service.py::list_events` |

## Couverture du cahier des charges

| Exigence | Mise en œuvre |
| --- | --- |
| Identifiant = numéro fiscal | 13 chiffres, validé côté client **et** serveur (`common/validation.py`) |
| Mot de passe ≥ 12 car., maj., min., chiffre, spécial | `password_problems()` appliqué à la création, à la réinitialisation et au changement par l'admin |
| MFA obligatoire par e-mail | code 6 chiffres, haché (HMAC) dans Redis, 5 min, 3 essais, usage unique, 3 renvois max |
| Jeton de session, SSO | jeton opaque aléatoire, stocké **haché** côté serveur (Redis), dans un cookie `__Host-` HttpOnly/Secure/SameSite=Strict ; expiration glissante 15 min, absolue 8 h ; la session survit au rechargement et est partagée par tous les services du portail |
| LDAP | OpenLDAP réel en LDAPS ; création/modification/suppression des comptes dans l'annuaire |
| RBAC (3 rôles) | rôle = groupe LDAP ; tableau des permissions du PDF intégralement appliqué (voir ci-dessous) |
| HTTPS/TLS sur tous les flux | navigateur→Nginx, Nginx→webapp, webapp→auth-system/log-collector, auth-system→LDAP (LDAPS) et →Mailpit (STARTTLS), tous vérifiés contre l'AC interne |
| PKI X.509 | service `pki` : AC racine ECDSA P-256 + certificats par service, renouvellement automatique |
| Hachage des mots de passe | `{CRYPT}` SHA-512-crypt salé, 200 000 itérations, vérifié par le serveur LDAP |
| Renouvellement des secrets | certificats renouvelés automatiquement ; `INTERNAL_SHARED_SECRETS` accepte plusieurs valeurs (rotation sans coupure) ; jetons régénérés à chaque connexion et révoqués à chaque changement de mot de passe ou de rôle |
| Portail admin (créer / modifier / supprimer) | onglet « Comptes », jeton admin dédié obligatoire |
| Menu des endpoints | tableau de bord généré par le serveur selon le rôle |
| Whitelist par endpoint, refus journalisé | décorateur `@access` sur chaque route de `webapp` (refus par défaut, vérifié au démarrage) + rôles par page ; chaque refus est journalisé |
| File d'attente, load balancer, montée en charge | Nginx `limit_req` avec *burst* (les requêtes excédentaires sont mises en file, pas rejetées), répartition `least_conn` ; services sans état → `docker compose up -d --scale webapp=3 --scale auth-system=2` puis `docker compose restart frontend` |
| Traçabilité (timestamp UTC, compte, action, endpoint, IP) | tous les événements, IP fixée par Nginx (non falsifiable) ; priorités `critical` (création/suppression de compte, droits ou mot de passe d'autrui, verrouillage), `high` (accès admin, réinitialisation, refus) |
| Protection des journaux | chaîne HMAC-SHA256 : toute modification est détectée (bouton « Vérifier l'intégrité ») |
| XSS / SQLi / injection de commande | validation par liste blanche de chaque champ, filtres LDAP échappés, aucune base SQL ni appel shell, rendu React échappé, CSP stricte sans script en ligne, cookies inaccessibles au JS |
| Anti brute-force | verrouillage du compte 15 min après 5 échecs, limitation par IP (échecs uniquement), limitation de débit Nginx, temps de réponse constant pour un compte inexistant |

### Modèle RBAC appliqué

| Permission | Externe | Agent | Admin |
| --- | :-: | :-: | :-: |
| Se connecter, réinitialiser son mot de passe | ✅ | ✅ | ✅ |
| Dashboard : se connecter, voir les pages | ✅ | ✅ | ✅ |
| Modifier les pages du dashboard (libellé, rôles, visibilité, ajout, suppression) | ❌ | ❌ | ✅ |
| Pages standard (`/page1.php`) | ✅ | ✅ | ✅ |
| Administration : accès, créer un compte, modifier les accès, le mot de passe d'un autre, supprimer | ❌ | ❌ | ✅ |

La page `/outils-agents.php` (agents et admins) sert d'exemple de page
restreinte. L'administrateur peut modifier ces règles depuis l'onglet
« Pages du tableau de bord ».

## Bugs corrigés par rapport à la v3

| Bug v3 | Correction |
| --- | --- |
| `frontend/Dockerfile` lançait `npm run dev` : l'image ne se construisait pas | `npm run build` (vérifie aussi le typage) |
| Sessions et annuaire simulé en mémoire **par worker gunicorn** (2 workers ⇒ jeton inconnu une fois sur deux, comptes créés perdus) | sessions dans Redis, annuaire OpenLDAP réel |
| `auth-system` sans `LOG_COLLECTOR_URL` dans Docker : tous ses journaux étaient perdus | variable fournie + repli sur la sortie standard |
| Injection LDAP : `(uid={fiscal_id})` sans échappement ni validation | validation stricte + `escape_filter_chars` |
| Secret inter-services comparé avec `!=` (attaque temporelle), unique et non renouvelable | `hmac.compare_digest`, plusieurs secrets acceptés |
| IP journalisée falsifiable via `X-Forwarded-For` | IP posée par Nginx (`X-Real-IP $remote_addr`) |
| Jetons en mémoire React : session perdue au rechargement | cookies HttpOnly + restauration de session |
| `MfaPage` appelait `navigate()` pendant le rendu | `<Navigate>` déclaratif |
| Erreurs 500 sur entrée invalide (`limit=abc`, JSON non objet…) | bornage et validation systématiques |
| Mots de passe hachés en SHA-1 (`{SSHA}`) | SHA-512-crypt 200 000 itérations |
| Code MFA stocké en clair, comparaison du jeton MFA non atomique | HMAC + suppression atomique (usage unique garanti) |
| Pas de réinitialisation de mot de passe, pas de gestion des comptes ni des pages, pas de verrouillage, pas de HTTPS | implémentés (voir tableau ci-dessus) |

## Tests

```bash
pip install -r backend/requirements-dev.txt

# 19 tests d'intégration en processus (LDAP simulé, Redis en mémoire) — ~2 s
python -m pytest tests -q

# Recette de bout en bout sur la pile Docker (56 vérifications) :
# HTTPS, cookies, MFA via Mailpit, RBAC, administration, journaux, verrouillage
docker compose cp pki:/pki/ca.crt ./ca.crt
python tests/e2e_smoke.py
```

Un seul test : `python -m pytest tests -q -k password_reset`.

## Développement sans Docker

```bash
pip install -r backend/requirements-dev.txt
python scripts/run_dev.py                       # webapp :5000, auth-system :5001, log-collector :5002
cd frontend && npm install && npm run dev       # http://localhost:5173
```

En mode développement : annuaire simulé (`LDAP_MODE=mock`), Redis en
mémoire, HTTP sans TLS, cookies non `Secure`, et le code 2FA est affiché
à l'écran (`DEBUG_EXPOSE_MFA_CODE=true` — **jamais en production**, le
service refuse d'ailleurs de démarrer avec `APP_ENV=production`).

## Structure

```
backend/
  common/          validation des entrées, appels inter-services (TLS + secret), client de logs
  auth-system/     auth_service.py (routes /internal/*), directory.py (LDAP), store.py (Redis), mailer.py
  webapp/          web_service.py (API publique, whitelist, cookies, CSRF)
  log-collector/   log_service.py (journal chaîné HMAC)
frontend/          React + TypeScript (Vite), nginx.conf
pki/               generate.py (AC + certificats)
tests/             tests pytest + recette e2e_smoke.py
```

## Limites connues (prototype pédagogique)

- `auth-system` se connecte à LDAP avec le compte `cn=admin` ; en
  production : compte de service dédié avec ACL restreintes.
- Redis et LDAP sont des instances uniques ; en production : Redis
  Sentinel/Cluster, réplication OpenLDAP, plusieurs nœuds Nginx.
- Le verrouillage de compte peut être déclenché volontairement par un
  tiers (déni de service ciblé) : compromis classique, atténué par la
  durée limitée (15 min) et le déverrouillage par l'administrateur.
- Le journal est un fichier JSONL ; en production : ELK/Graylog/SIEM.
