# Portail Sécurisé DGFiP — backend distribué + frontend React/TS

Projet organisé en **4 parties strictement séparées**, chacune dans son
propre dossier, sa propre image Docker, ses propres dépendances :

```
.
├── backend/
│   ├── webapp/          "Application Web"          → seul service qui parle au frontend
│   ├── auth-system/     "Système d'authentification" (LDAP) → jamais exposé
│   └── log-collector/   "Puits de logs"                     → jamais exposé
├── frontend/             React + TypeScript, servi par Nginx
├── docker-compose.yml
└── .env.example
```

Ce découpage suit exactement les entités du schéma fourni
(`ArchiWebDistribuée_drawio.svg`) et ses 13 flux numérotés (tableau de
correspondance plus bas).

## Architecture réseau (Docker)

```
                              Internet / utilisateur
                                       │
                                       │  HTTPS (à terminer devant, cf. plus bas)
                                       ▼
                          ┌───────────────────────┐
                          │   frontend (Nginx)      │  ◀── SEUL service publié sur l'hôte
                          │   port hôte 80 → 8080     │
                          └───────────┬───────────┘
                                       │  réseau "edge"
                                       ▼
                          ┌───────────────────────┐
                          │   webapp                 │  ◀── jamais publié sur l'hôte
                          └──────┬──────────┬───────┘
                                 │ réseau "core" (internal: true — aucune sortie Internet)
                    ┌────────────┘          └────────────┐
                    ▼                                     ▼
        ┌───────────────────────┐            ┌───────────────────────┐
        │   auth-system (LDAP)     │            │   log-collector          │
        └───────────────────────┘            └───────────────────────┘
```

- **Un seul port est exposé à l'extérieur** : celui du frontend. `webapp`,
  `auth-system` et `log-collector` n'ont **aucune** entrée `ports:` dans
  `docker-compose.yml` — ils ne sont routables que depuis les autres
  conteneurs du même réseau Docker, jamais depuis l'hôte ni Internet.
- Le réseau `core` est marqué `internal: true` : les 3 services
  backend ne peuvent ni recevoir de connexion externe, ni initier de
  connexion sortante vers Internet, même en cas de compromission.
- `auth-system` et `log-collector` ne sont même pas présents sur le
  réseau `edge` : le frontend ne peut physiquement pas les atteindre,
  seul `webapp` le peut.
- Le navigateur n'appelle jamais `webapp` par son nom/IP Docker : Nginx
  relaie `/api/*` en interne (voir `frontend/nginx.conf`). Un seul nom
  d'hôte public existe.

## « On ne doit pas pouvoir voir le code dans l'inspecteur »

Point important à clarifier honnêtement : **du code JavaScript qui
s'exécute dans le navigateur est, par nature, toujours livré au
navigateur** — l'inspecteur pourra toujours afficher le JS/CSS/HTML
final envoyé (c'est vrai pour n'importe quel site React/Vue/Angular,
Google ou Facebook inclus). Il n'existe aucun moyen de faire tourner du
code côté client tout en le rendant totalement invisible. Ce qui est
en revanche fait ici, et qui est la pratique standard pour ce
problème :

- **Aucune source map n'est générée** (`vite.config.ts :: build.sourcemap = false`)
  → l'inspecteur affiche un bundle minifié en une ligne, pas le
  TypeScript/JSX d'origine avec noms de variables et commentaires.
- **Minification + build de production** (`vite build`, `esbuild`) →
  noms de variables raccourcis, code mort supprimé, `console.log`/
  `debugger` retirés.
- **Aucun fichier source dans l'image finale** : le `Dockerfile` du
  frontend est multi-étapes — l'image livrée ne contient que
  `dist/` (le bundle compilé), ni `src/`, ni `node_modules`, ni
  `package.json`. Il n'y a littéralement rien d'autre à servir même en
  cas de mauvaise configuration.
- Toute logique réellement sensible (validation des identifiants,
  vérification du rôle, décision d'autoriser une page, secrets,
  jetons) **vit côté serveur** (les 3 services backend), jamais dans
  le bundle React — le front ne fait qu'afficher ce que le backend lui
  autorise à voir. C'est la seule vraie garantie de sécurité : ne
  jamais faire confiance au code exécuté côté client.

## Déploiement avec Docker (recommandé)

Prérequis : Docker + Docker Compose v2 (`docker compose version`).

```bash
cp .env.example .env
# éditer .env : au minimum INTERNAL_SHARED_SECRET (openssl rand -hex 32)
# et LDAP_BIND_PASSWORD

docker compose up --build -d
docker compose ps          # les 4 services doivent passer "healthy"
```

L'application est accessible sur `http://localhost` (port configurable
via `HTTP_PORT` dans `.env`). Tout le reste (webapp, auth-system,
log-collector) est injoignable depuis l'extérieur — testez-le :

```bash
curl http://localhost:5000   # échoue : port non publié
curl http://localhost:5001   # échoue : port non publié
curl http://localhost:5002   # échoue : port non publié
curl http://localhost/api/health   # fonctionne : relayé par Nginx vers webapp
```

Arrêter : `docker compose down` (ajouter `-v` pour aussi supprimer le
volume `log-data`, donc l'historique des logs).

### Durcissement déjà appliqué dans `docker-compose.yml`

| Mesure | Effet |
| --- | --- |
| `cap_drop: [ALL]` sur tous les services | Retire toutes les capabilities Linux inutiles au conteneur |
| `security_opt: [no-new-privileges:true]` | Empêche l'escalade de privilèges même via un binaire setuid |
| `read_only: true` + `tmpfs` ciblés | Système de fichiers racine en lecture seule ; seuls `/tmp` (et `/data` pour log-collector, via volume nommé) sont inscriptibles |
| `USER` non-root dans chaque `Dockerfile` | Aucun processus ne tourne en `root` dans les conteneurs |
| Images `-slim`/`-alpine`, builds multi-étapes | Surface d'attaque minimale, pas d'outils de compilation dans l'image finale |
| `HEALTHCHECK` sur les 4 services | Détection automatique d'un service défaillant (`docker compose ps`) |
| `restart: unless-stopped` | Redémarrage automatique en cas de crash |

### Passer en HTTPS

Ce `docker-compose.yml` sert du HTTP en clair sur le port choisi — à
usage local ou derrière un reverse proxy qui termine le TLS (Traefik,
Caddy, Nginx externe avec Let's Encrypt, ou le load balancer d'un
fournisseur cloud). Ne jamais exposer directement ce port 80 sur
Internet sans TLS devant. Si vous n'avez pas déjà un tel reverse proxy,
[Caddy](https://caddyserver.com/) est l'option la plus simple à
ajouter en conteneur supplémentaire devant `frontend`.

## Lancer chaque service individuellement, sans Docker (dev)

Utile pour déboguer un seul service. Chaque dossier reste autonome
avec son propre `requirements.txt`/`package.json` et son propre
`.env.example` (distinct du `.env` racine utilisé par Docker) :

```bash
# terminal 1
cd backend/log-collector && pip install -r requirements.txt && cp .env.example .env && python app.py

# terminal 2
cd backend/auth-system && pip install -r requirements.txt && cp .env.example .env && python app.py

# terminal 3
cd backend/webapp && pip install -r requirements.txt && cp .env.example .env && python app.py

# terminal 4
cd frontend && npm install && cp .env.example .env && npm run dev   # http://localhost:5173
```

En dehors de Docker, `FLASK_DEBUG=true` peut être positionné dans les
`.env` de chaque service pour activer le rechargement à chaud — ne
jamais faire ça en production (le `Dockerfile` utilise de toute façon
`gunicorn`, qui ignore ce réglage).

## Comptes de démonstration (annuaire LDAP simulé)

| Rôle | Numéro fiscal | Mot de passe |
| --- | --- | --- |
| Agent DGFiP | `1032005849213` | `Agent!DGFiP2026` |
| Utilisateur externe | `2098741562034` | `Usager!Externe26` |
| Administrateur système | `3011008876521` | `Admin!SysDGFiP26` |

`DEBUG_EXPOSE_MFA_CODE=true` (à ne **jamais** activer en production)
renvoie le code 2FA dans la réponse JSON pour tester sans serveur de
messagerie réel.

## Correspondance flux du schéma → code

| Flux | Description (légende du schéma) | Où dans le code |
| --- | --- | --- |
| 1 | POST `/login.php` avec login/password | `backend/webapp/app.py :: login()` |
| 2/3 | Validation des identifiants contre LDAP | `backend/auth-system/app.py :: check_credentials()` + `ldap_directory.py` |
| 4 | Envoi du code 2FA par e-mail | `backend/auth-system/app.py :: _send_2fa_email()` |
| 5 | Validation du code 2FA ou terminaison de session | `backend/auth-system/app.py :: verify_2fa()` |
| 6 | Redirection vers `/dashboard.php` | `backend/webapp/app.py :: login_verify_2fa()` → `frontend` navigue vers `/dashboard` |
| 7/8 | Vérification du rôle vs rôles autorisés pour la page | `backend/auth-system/app.py :: rbac_check()` + `PAGE_RBAC` |
| 9 | Redirection vers l'endpoint souhaité | `backend/webapp/app.py :: dashboard()` / `page1()` |
| 10 | Vérification de l'appartenance au groupe admin LDAP | `ldap_directory.py :: is_admin()` |
| 11 | Échange du token de session contre un token admin scopé `/admin.php` | `backend/auth-system/app.py :: admin_exchange()` |
| 12 | Collecte et centralisation des événements | `logging_client.py :: send_log()` → `backend/log-collector/app.py :: ingest_event()` |
| 13 | Collecte, priorisation des événements de session admin | Même chemin, `priority="high"` ; log-collector les trie en tête ; `frontend` les affiche dans `/admin` |

Le modèle RBAC est porté par LDAP (groupes `cn=externes`, `cn=agents`,
`cn=admins`), pas par un champ libre en base.

## Frontend — pages

`LoginPage` (flux 1) → `MfaPage` (flux 4/5/6) → `DashboardPage` (flux
6/7/8/9, liens générés dynamiquement selon le rôle) → `Page1Page`
(exemple de « tout autre endpoint ») → `AdminGatePage` (flux 10/11) →
`AdminPage` (flux 12/13, journal de traçabilité).

Les jetons ne sont conservés qu'en mémoire React (jamais
`localStorage`) : une session se termine au rechargement de la page.

## Passer à un vrai annuaire LDAP

`backend/auth-system/ldap_directory.py` utilise par défaut un
annuaire simulé en mémoire (`ldap3`, `MOCK_SYNC`) — zéro dépendance
externe. Pour un vrai serveur LDAP (OpenLDAP, Active Directory…),
positionner dans `.env` :

```
LDAP_MODE=real
LDAP_HOST=ldap.dgfip.interne
LDAP_PORT=636
LDAP_USE_SSL=true
LDAP_BASE_DN=dc=dgfip,dc=fr
LDAP_BIND_DN=cn=auth-system,dc=dgfip,dc=fr
LDAP_BIND_PASSWORD=...
```

Le code de recherche/authentification/RBAC est strictement identique
dans les deux modes.
