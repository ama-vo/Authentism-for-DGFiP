# Portail Sécurisé DGFiP — Prototype Authentism

Implémentation de référence du cahier des charges : API **Flask** (Python) +
interface **React / TypeScript**. Couvre l'identification par numéro fiscal,
le MFA par e-mail, le SSO, le RBAC avec liste d'autorisation par endpoint, le
panneau d'administration (jeton dédié + CRUD comptes) et le journal de
traçabilité horodaté.

> Prototype pédagogique. Avant toute mise en production : TLS de bout en
> bout, vrai fournisseur d'e-mail transactionnel, stockage des jetons en
> base de production (PostgreSQL), durcissement CSP/HSTS au niveau du
> reverse proxy, file d'attente et répartition de charge au niveau
> infrastructure (§3.1 du cahier des charges).

## Arborescence

```
backend/     API Flask (SQLAlchemy, sessions serveur, RBAC, journalisation)
frontend/    Application React + TypeScript (Vite)
```

## 1. Lancer le backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate   # ou l'équivalent Windows
pip install -r requirements.txt
cp .env.example .env                                 # puis adapter SECRET_KEY
python app.py
```

L'API démarre sur `http://localhost:5000`. Au premier lancement, trois
comptes de démonstration sont créés automatiquement (voir `backend/seed.py`) :

| Rôle | Numéro fiscal | Mot de passe |
| --- | --- | --- |
| Agent DGFiP | `1032005849213` | `Agent!DGFiP2026` |
| Utilisateur externe | `2098741562034` | `Usager!Externe26` |
| Administrateur système | `3011008876521` | `Admin!SysDGFiP26` |

`DEBUG_EXPOSE_MFA_CODE=true` (dans `.env`) affiche le code MFA dans la
réponse JSON pour permettre de tester le parcours sans serveur de
messagerie réel. **À retirer impérativement en production** — le code doit
uniquement partir par e-mail (`_send_mfa_email` dans `auth_routes.py` est le
point d'intégration du fournisseur d'e-mail réel).

## 2. Lancer le frontend

```bash
cd frontend
npm install
cp .env.example .env      # VITE_API_URL doit pointer vers l'API Flask
npm run dev
```

L'application est servie sur `http://localhost:5173`.

## 3. Parcours de test

1. `/login` — se connecter avec un des comptes de démonstration.
2. `/mfa` — saisir le code affiché dans l'encart de démonstration.
3. `/portail` — les tuiles grisées correspondent aux services hors liste
   d'autorisation pour le rôle courant (RBAC, §2.5).
4. Avec le compte administrateur : cliquer sur « Panneau d'administration »
   → ressaisir le mot de passe pour obtenir le second jeton dédié (§2.4) →
   gérer les comptes et consulter le journal de traçabilité (§3.2).

## Points du cahier des charges couverts côté code

| Exigence | Implémentation |
| --- | --- |
| §2.1 Politique de mot de passe | `security.validate_password` (backend) + `utils/validation.ts` (frontend) |
| §2.1 MFA par e-mail | `auth_routes.py` (`/auth/login`, `/auth/mfa/verify`) |
| §2.2 Jeton de session stocké serveur | Modèle `Session` (SQLAlchemy), jamais de JWT auto-porteur |
| §2.2 SSO | Un seul jeton pour l'ensemble des services normaux |
| §2.2 RBAC | Champ `role` sur `User`, décorateur `require_session(roles=...)` |
| §2.3 Hachage des mots de passe | `werkzeug.security` (PBKDF2-SHA256, 600 000 itérations) |
| §2.4 Portail admin + jeton dédié | `Session.scope == "admin"`, endpoint `/admin/token` |
| §2.5 Liste d'autorisation par endpoint | `SERVICE_WHITELIST` dans `services_routes.py` |
| §3.2 Traçabilité | Modèle `AuditLog`, fonction `log_event`, priorité élevée pour les actions sensibles |
| §3.3 Résistance aux injections | ORM SQLAlchemy (pas de SQL brut), validation stricte des entrées, React échappe le rendu par défaut |

Les exigences purement infrastructurelles (§3.1 : file d'attente,
répartiteur de charge, montée en charge horizontale) relèvent du
déploiement (reverse proxy, orchestrateur, base de données répliquée) et ne
sont pas du ressort du code applicatif — `Flask-Limiter` est toutefois déjà
en place comme première ligne de défense contre le bourrage de requêtes sur
les endpoints d'authentification.
