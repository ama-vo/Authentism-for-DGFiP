# Backend distribué — conforme au schéma « Archi Web Distribuée »

Ce backend est découpé en **trois microservices**, un par entité du
schéma fourni (`ArchiWebDistribuée_drawio.svg`), qui communiquent
uniquement comme les flèches du schéma le montrent :

```
Navigateur
    │  (HTTP public)
    ▼
┌─────────────────────┐        ┌──────────────────────────────┐
│   webapp (5000)      │──────▶│   auth-system (5001)          │
│  "Application Web"    │◀──────│ "Système d'authentification"  │
│  /login.php            │       │  (LDAP mock ou réel)          │
│  /dashboard.php         │      └───────────────┬────────────────┘
│  /page1.php               │                     │ (flux 12/13)
│  /admin.php                 │                    ▼
└─────────────────────┘        ┌──────────────────────────────┐
                                 │   log-collector (5002)         │
                                 │      "Puits de logs"             │
                                 └──────────────────────────────┘
```

`webapp` est le **seul** service exposé au navigateur. `auth-system` et
`log-collector` ne sont accessibles que sur le réseau interne (dans ce
prototype : `localhost`, en production : un réseau privé/VPC, jamais
routable depuis Internet), et protégés par un secret partagé
(`INTERNAL_SHARED_SECRET`) qui simule une authentification
service-à-service (à remplacer par du mTLS en production).

## Correspondance flux du schéma → code

| Flux | Description (légende du schéma) | Où dans le code |
| --- | --- | --- |
| 1 | POST `/login.php` avec login/password | `webapp/app.py :: login()` |
| 2/3 | Validation des identifiants contre LDAP | `auth-system/app.py :: check_credentials()` + `ldap_directory.py :: check_credentials()` |
| 4 | Envoi du code 2FA par e-mail | `auth-system/app.py :: _send_2fa_email()` |
| 5 | Validation du code 2FA ou terminaison de session | `auth-system/app.py :: verify_2fa()` |
| 6 | Redirection vers `/dashboard.php` | `webapp/app.py :: login_verify_2fa()` (champ `redirect`) |
| 7/8 | Vérification du rôle vs rôles autorisés pour la page | `auth-system/app.py :: rbac_check()` + `PAGE_RBAC` |
| 9 | Redirection vers l'endpoint souhaité | `webapp/app.py :: dashboard()` / `page1()` |
| 10 | Vérification de l'appartenance au groupe admin LDAP | `ldap_directory.py :: is_admin()` |
| 11 | Échange du token de session contre un token admin scopé `/admin.php` | `auth-system/app.py :: admin_exchange()` |
| 12 | Collecte et centralisation des événements | `auth-system/logging_client.py :: send_log()` → `log-collector/app.py :: ingest_event()` |
| 13 | Collecte, priorisation des événements de session admin | Même chemin, avec `priority="high"` ; `log-collector` trie les événements `high` en tête |

Le modèle RBAC est bien porté par LDAP (groupes `cn=externes`,
`cn=agents`, `cn=admins`), pas par un simple champ en base — comme le
montre le nœud « Modèle RBAC (LDAP) » du schéma.

## Frontend (React + TypeScript)

`frontend/` est une application React/TS (Vite) qui ne parle qu'à
`webapp` — jamais directement à `auth-system` ni à `log-collector`,
exactement comme le schéma l'impose (seule l'Application Web est
exposée au navigateur).

```bash
cd frontend
npm install
cp .env.example .env      # VITE_API_URL doit pointer vers webapp (port 5000)
npm run dev                # http://localhost:5173
```

Pages : `/login` (flux 1) → `/mfa` (flux 4/5/6) → `/dashboard` (flux
6/7/8/9, liens générés dynamiquement selon le rôle) → `/page1`
(exemple de « tout autre endpoint ») → `/admin/gate` (flux 10/11,
échange de jeton) → `/admin` (flux 12/13, panneau + journal
priorisé).

## Lancer les trois services back

Chaque service est indépendant (son propre `requirements.txt`,
son propre `.env.example`). Il faut les trois pour un parcours complet.

```bash
# terminal 1
cd log-collector && pip install -r requirements.txt && cp .env.example .env && python app.py

# terminal 2
cd auth-system && pip install -r requirements.txt && cp .env.example .env && python app.py

# terminal 3
cd webapp && pip install -r requirements.txt && cp .env.example .env && python app.py
```

`INTERNAL_SHARED_SECRET` doit être **identique** dans les trois `.env`.

## Comptes de démonstration (annuaire LDAP simulé)

| Rôle | Numéro fiscal | Mot de passe |
| --- | --- | --- |
| Agent DGFiP | `1032005849213` | `Agent!DGFiP2026` |
| Utilisateur externe | `2098741562034` | `Usager!Externe26` |
| Administrateur système | `3011008876521` | `Admin!SysDGFiP26` |

`DEBUG_EXPOSE_MFA_CODE=true` (dans `auth-system/.env`) renvoie le code
2FA dans la réponse JSON pour tester sans serveur de messagerie réel —
**à retirer en production**.

## Parcours de test (curl)

```bash
# 1. Login
curl -X POST http://localhost:5000/login.php \
  -H "Content-Type: application/json" \
  -d '{"fiscal_id":"3011008876521","password":"Admin!SysDGFiP26"}'
# -> { pending_token, debug_code }

# 2. Validation 2FA
curl -X POST http://localhost:5000/login.php/verify \
  -H "Content-Type: application/json" \
  -d '{"pending_token":"...","code":"..."}'
# -> { token, role, fiscal_id, redirect: "/dashboard.php" }

# 3. Dashboard (liste des endpoints accessibles selon le rôle)
curl http://localhost:5000/dashboard.php -H "Authorization: Bearer <token>"

# 4. Échange vers un jeton admin scopé, puis accès à /admin.php
curl -X POST http://localhost:5000/admin.php/token -H "Authorization: Bearer <token>"
curl http://localhost:5000/admin.php -H "Authorization: Bearer <admin_token>"

# 5. Journal centralisé, événements admin priorisés en tête
curl "http://localhost:5002/logs?limit=20"
```

## Passer à un vrai annuaire LDAP

`auth-system/ldap_directory.py` utilise par défaut un annuaire simulé
en mémoire (`ldap3`, stratégie `MOCK_SYNC`) — aucune dépendance externe
requise pour faire tourner ce prototype. Pour brancher un vrai serveur
LDAP (OpenLDAP, Active Directory…), positionner dans `auth-system/.env` :

```
LDAP_MODE=real
LDAP_HOST=ldap.dgfip.interne
LDAP_PORT=636
LDAP_USE_SSL=true
LDAP_BASE_DN=dc=dgfip,dc=fr
LDAP_BIND_DN=cn=auth-system,dc=dgfip,dc=fr
LDAP_BIND_PASSWORD=...
```

Le reste du code (recherche, RBAC par groupe, vérification de mot de
passe) est strictement identique dans les deux modes.

## Ce qui reste volontairement hors de ce backend

Comme pour le prototype précédent, la scalabilité pure
infrastructure (file d'attente, répartiteur de charge, montée en
charge horizontale) se règle au niveau du déploiement (reverse proxy,
orchestrateur), pas dans le code applicatif de ces trois services.
