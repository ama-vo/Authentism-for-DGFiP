# Authentism × DGFiP — Système d'authentification sécurisé

Projet réalisé pour la Direction générale des Finances publiques : portail d'authentification
avec MFA, SSO, connexion à l'annuaire LDAP existant, contrôle d'accès par rôles (RBAC), journalisation et protection
contre les injections.

**Stack :** React + TypeScript (frontend) · Node.js + Express + TypeScript (API) · annuaire
LDAP existant · Redis · PostgreSQL · nginx · Docker Compose.

---

## 🚀 Lancer le projet

Prérequis : Docker et Docker Compose.

```bash
cp .env.example .env          # OBLIGATOIRE
docker compose up --build     # toujours --build après une modification du code
```

| Adresse | Rôle |
| --- | --- |
| https://localhost | Le portail (accepter l'avertissement du certificat, voir plus bas) |
| http://localhost:8025 | Boîte mail de test : **les codes MFA arrivent ici** |

### Mode test (par défaut) : pas besoin de vrai LDAP

Le `.env` par défaut contient `COMPOSE_PROFILES=test` : un **LDAP de test** (service `ldap-test`)
démarre automatiquement avec ces comptes (`ldap/ldap-test.ldif`) :

| Numéro fiscal | Mot de passe de connexion | Rôle |
| --- | --- | --- |
| `1000000000001` | `Admin#Dgfip2026!` | Administrateur |
| `2000000000002` | `Agent#Dgfip2026!` | Agent DGFiP |
| `3000000000003` | `Usager#Dgfip2026!` | Utilisateur externe |

Pour ouvrir le **panneau d'administration**, l'admin utilise un **second mot de passe**,
différent : `AdminPanel#2026!` (compte d'administration dans `ou=admins`).

### Mode production : connexion au vrai annuaire de la DGFiP

Dans `.env` : supprimer `COMPOSE_PROFILES=test` et remplir les variables LDAP.

| Variable | Exemple | Rôle |
| --- | --- | --- |
| `LDAP_URL` | `ldaps://ldap.dgfip.local:636` | Adresse du serveur (`ldaps://` = chiffré, obligatoire en production) |
| `LDAP_BIND_DN` | `cn=app-authentism,dc=dgfip,dc=local` | Compte de service de l'application |
| `LDAP_BIND_PASSWORD` | | Son mot de passe |
| `LDAP_USERS_DN` | `ou=users,dc=dgfip,dc=local` | Branche qui contient les comptes |
| `LDAP_ADMINS_DN` | `ou=admins,dc=dgfip,dc=local` | Branche des comptes d'administration (mot de passe du panneau admin) |
| `LDAP_LOGIN_ATTRIBUTE` | `uid` | Attribut contenant le numéro fiscal |
| `LDAP_ROLE_ATTRIBUTE` | `employeeType` | Attribut contenant le rôle (`usager`, `agent`, `admin`) |

- Si le certificat du LDAP est signé par une CA interne, la copier dans `ldap/ca.crt`.
- Chaque compte doit avoir une adresse `mail` (le code MFA y est envoyé).
- `ldap/exemple-comptes.ldif` permet d'ajouter des comptes de test dans un vrai annuaire.

### Vérifier que l'annuaire est bien connecté

```bash
docker compose logs backend | grep ldap
```
Le message `[ldap] Connecté à ... N compte(s) trouvé(s)` doit apparaître (jusqu'à 1 minute après le démarrage).

### Faire confiance au certificat (optionnel)

Le certificat HTTPS est signé par notre propre autorité de certification. Pour supprimer
l'avertissement du navigateur, récupérer la CA et l'importer dans le navigateur :

```bash
docker compose cp web:/etc/nginx/certs/ca.crt ./authentism-ca.crt
```

---

## 🏗️ Architecture

```
Navigateur ──HTTPS──▶  web (nginx)
                        │  • TLS (certificat de la PKI)
                        │  • file d'attente + limitation du trafic
                        │  • répartiteur de charge
                        │  • sert le frontend React
                        ▼
                 backend × 2 (API Express)   ◀── whitelist.ts contrôle CHAQUE requête
                        │
      ┌─────────────────┼──────────────────┬──────────────┐
      ▼                 ▼                  ▼              ▼
  LDAP existant     redis              postgres         mail
  (ldaps://)    sessions, codes MFA   journaux, pages, codes MFA,
  identités     compteurs d'échecs    âge des mots     liens reset
  + rôles                             de passe
```

Le réseau `back` est **interne** : Redis et PostgreSQL ne sont pas joignables depuis l'extérieur.
Seule l'API a un accès sortant (réseau `ldap`) pour joindre l'annuaire.

### Arborescence

```
authentism/
├── docker-compose.yml
├── .env.example
├── pki/generate.sh          # autorité de certification + certificat X.509 du site
├── ldap/                    # LDAP de test, ca.crt du vrai LDAP (si besoin), exemple de comptes
├── postgres/init.sql        # tables audit_logs, pages, password_changes
├── backend/src/
│   ├── index.ts             # point d'entrée de l'API
│   ├── whitelist.ts         # ⭐ liste d'autorisation des endpoints (RBAC)
│   ├── session.ts           # jetons de session stockés dans Redis
│   ├── ldap.ts              # connexion à l'annuaire existant
│   ├── passwordAge.ts       # renouvellement des mots de passe (90 jours)
│   ├── validation.ts        # règles de validation (anti-injection)
│   ├── audit.ts             # journal d'audit
│   └── routes/              # auth.ts, pages.ts, admin.ts
└── frontend/
    ├── nginx.conf           # HTTPS, file d'attente, load balancer
    └── src/                 # application React
        ├── pages/           # Login, Dashboard, Admin, ...
        └── components/
```

---

## ✅ Correspondance avec le cahier des charges

### 2.1 Identification et authentification
- Identifiant = **numéro fiscal** (13 chiffres, validé côté client ET serveur).
- Mot de passe : **12 caractères min., majuscule, minuscule, chiffre, caractère spécial**
  (`validation.ts`, affiché en direct dans le formulaire).
- **MFA obligatoire** : après le mot de passe, un code à 6 chiffres est envoyé à l'adresse
  e-mail du compte (valable 5 min, 3 essais max, usage unique).
- Messages d'erreur identiques que le compte existe ou non (pas d'énumération des comptes).
- Blocage du compte 15 min après 5 échecs.

### 2.2 Identités et sessions
- **Jeton de session** aléatoire (256 bits) dans un cookie `HttpOnly`, `Secure`, `SameSite=Strict`.
- **Périmètre défini à l'avance** : jeton `user` (dashboard + pages) ou jeton `admin`.
- **SSO** : une seule connexion donne accès à tous les services du dashboard ; la session
  est partagée entre tous les réplicas de l'API grâce à Redis.
- **LDAP** : les identités (numéro fiscal, nom, e-mail, rôle, mot de passe) restent
  centralisées dans l'annuaire existant. Le mot de passe est vérifié par un **bind LDAP**
  avec le compte de l'utilisateur : l'API ne lit jamais les mots de passe.
- **RBAC** : 3 rôles (`usager`, `agent`, `admin`) appliqués selon le tableau des permissions.

### 2.3 Chiffrement et secrets
- HTTPS/TLS 1.2+ obligatoire : seul le port 443 est exposé, HSTS activé.
- **PKI** (`pki/generate.sh`) : une CA signe le certificat X.509 du site.
- L'API parle à l'annuaire en **LDAPS** en vérifiant son certificat (`ldap/ca.crt`).
- Mots de passe hachés **par l'annuaire** : les changements passent par l'opération LDAP
  standard *Password Modify* (RFC 3062), l'annuaire applique sa politique de hachage
  (`olcPasswordHash` sous OpenLDAP — privilégier `{SSHA512}` ou `{ARGON2}` si disponible).
- Renouvellement des secrets : sessions de 30 min (15 min pour l'admin), mot de passe à
  renouveler tous les **90 jours**, sessions révoquées à chaque changement de mot de passe
  ou de rôle, certificats de 397 jours.
- Jetons de session, codes MFA et liens de réinitialisation **stockés côté serveur** (Redis).
  Les codes et liens sont stockés hachés.

### 2.4 Administration
- Portail `/admin` : créer, modifier (rôle, mot de passe), supprimer un compte ; gérer les
  pages du dashboard ; consulter les journaux.
- Accès : compte admin connecté **+ mot de passe d'administration**, différent du mot de passe
  de connexion → jeton de session dédié à l'administration (15 min).
- Chaque administrateur a **deux comptes LDAP** : son compte habituel (`ou=users`) et un
  **compte d'administration** (`ou=admins`). Voler le mot de passe de connexion ne suffit donc
  pas pour administrer (séparation des comptes à privilèges, recommandation ANSSI).
- L'application **impose que les deux mots de passe soient différents** (création, promotion,
  changement par l'admin, réinitialisation).
- 5 échecs sur le mot de passe d'administration → panneau bloqué 15 min (journalisé `CRITIQUE`).
- Passer un compte admin → création de son compte d'administration ; le rétrograder ou le
  supprimer → suppression de son compte d'administration.

### 2.5 Accès aux endpoints
- `backend/src/whitelist.ts` : **chaque endpoint** est listé avec les rôles autorisés.
  Tout ce qui n'est pas listé est refusé (403) et **le refus est journalisé**.

### 3.1 Montée en charge (pic de 20 millions d'utilisateurs)
- **File d'attente** nginx sur l'authentification : au-delà du débit autorisé, les requêtes
  attendent leur tour au lieu de surcharger l'API ; si la file est pleine, l'utilisateur
  voit « Le service est très sollicité ».
- **Load balancer** nginx entre les réplicas de l'API.
- **Scalabilité horizontale** : l'API est sans état (tout est dans Redis/LDAP/PostgreSQL),
  on peut donc ajouter des réplicas :
  ```bash
  docker compose up -d --scale backend=6
  docker compose restart web      # pour que nginx découvre les nouveaux réplicas
  ```

### 3.2 Traçabilité
Chaque événement contient : **timestamp UTC, compte, action, endpoint, adresse IP**, plus la
priorité, le succès/échec et des détails. Il est écrit dans PostgreSQL et affiché en JSON :

```bash
docker compose logs -f backend
```

| Priorité | Exemples |
| --- | --- |
| `CRITIQUE` | accès au panneau d'administration, création/suppression de compte, changement de rôle ou de mot de passe par l'admin |
| `ELEVE` | réinitialisation de mot de passe, compte bloqué, accès refusé |
| `INFO` | connexion réussie, déconnexion, consultation de page |

### 3.3 Résistance aux injections
| Attaque | Protection |
| --- | --- |
| **Injection SQL** | requêtes paramétrées uniquement (`$1, $2…`), jamais de concaténation |
| **Injection LDAP** | `EqualityFilter` qui échappe les caractères spéciaux + numéro fiscal limité à 13 chiffres ; mot de passe vide refusé (évite la connexion anonyme) |
| **XSS** | React échappe tout l'affichage (aucun `dangerouslySetInnerHTML`), Content-Security-Policy stricte, cookies `HttpOnly` |
| **Injection de commandes** | l'API n'exécute aucune commande système |
| **Toutes** | validation par liste blanche (`zod`) de chaque champ : format, longueur, caractères autorisés ; corps de requête limité à 10 Ko |

---

## 🧪 Tester rapidement

1. Se connecter en **usager** → le code arrive sur http://localhost:8025 → dashboard.
2. Taper `https://localhost/admin` → redirection : l'usager n'y a pas accès.
3. Se connecter en **admin** → tuile « Administration » → ressaisir le mot de passe.
4. Masquer une page dans « Pages du dashboard » → elle disparaît chez l'usager.
5. Onglet « Journaux » → filtrer sur `CRITIQUE`.

## 🔁 Remettre à zéro

```bash
docker compose down -v      # supprime les données locales (base, certificats) - l'annuaire LDAP n'est pas touché
```

## 🛠️ Dépannage

| Problème | Solution |
| --- | --- |
| `required variable ... is missing a value` | Créer le fichier `.env` : `cp .env.example .env` puis le remplir |
| `container postgres exited (1)` | Mot de passe vide : vérifier `.env`, puis `docker compose down -v` et relancer |
| `failed to bind host port ...:443` | Un autre logiciel utilise le port 443 : l'arrêter, ou remplacer `"443:443"` par `"8443:443"` dans `docker-compose.yml` et ouvrir https://localhost:8443 |
| `backend exited with code 1` | Lire la cause : `docker compose logs backend`. Souvent une ancienne image : relancer avec `docker compose up --build` |
| `[ldap] ERREUR de connexion` dans les logs | Vérifier `LDAP_URL` (avec `host.docker.internal` si le LDAP est sur votre machine), le compte de service et `ldap/ca.crt` |
| Connexion refusée pour un compte qui existe | Le compte doit avoir le numéro fiscal (13 chiffres) dans `uid`, un `mail`, et être sous `LDAP_USERS_DN` |

## ⚠️ Limites connues (projet pédagogique)

- Le serveur mail est un serveur de test (Mailpit) : en production, utiliser un vrai relais SMTP chiffré.
- Les flux internes Redis / PostgreSQL / SMTP circulent en clair sur le réseau Docker interne
  (seuls le web et la connexion à l'annuaire LDAP sont en TLS).
- Le compte de service LDAP doit avoir les droits de création/modification dans `LDAP_USERS_DN`
  pour que le portail d'administration fonctionne ; lui donner le minimum de droits nécessaires.
