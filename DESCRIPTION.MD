# Cahier des charges

| Élément | Détail |
| --- | --- |
| **Client** | Direction générale des Finances publiques (DGFiP) |
| **Maître d'œuvre** | Authentism |
| **Besoin** | Créer un système d'authentification robuste pour les différents services de la DGFiP. |
| **Date de rendu** | À définir |

## 1. Introduction

### 1.1 Contexte

La Direction générale des Finances publiques (DGFiP) a récemment été victime d'une cyberattaque de grande ampleur liée à son système d'authentification. Elle souhaite donc revoir son système de gestion des identités et des accès.

La DGFiP a mandaté **Authentism**, société spécialisée dans la sécurité des systèmes d'information et la gestion des identités et des accès (*Identity and Access Management*, IAM).

### 1.2 Objectif du projet

Concevoir une architecture d'authentification sécurisée, disponible à grande échelle et adaptée aux différents services de la DGFiP. La sécurité constitue la priorité de la solution, tout en conservant une expérience utilisateur fluide grâce au SSO.

## 2. Proposition technique

### 2.1 Identification et authentification

L'accès aux services de la DGFiP se fera depuis un portail d'authentification reposant sur un identifiant et un mot de passe.

**Règles d'authentification :**

- l'identifiant est le numéro fiscal de l'utilisateur ;
- le mot de passe comporte au minimum 12 caractères ;
- le mot de passe contient au moins une majuscule, une minuscule, un chiffre et un caractère spécial ;
- une authentification multifacteur (MFA) est obligatoire ;
- le second facteur est un code envoyé à l'adresse e-mail associée au compte.

### 2.2 Gestion des identités et des sessions

Après authentification, l'identité de l'utilisateur est représentée par un **jeton de session** dont le périmètre est défini à l'avance.

Cette approche permet :

- la mise en place d'un **Single Sign-On (SSO)** entre les services ;
- la gestion centralisée des identités avec le protocole **LDAP** (*Lightweight Directory Access Protocol*) ;
- un contrôle d'accès basé sur les rôles (**RBAC**).

**Rôles prévus :**

1. utilisateur externe ;
2. agent de la DGFiP ;
3. administrateur système.

### 2.3 Chiffrement et protection des secrets

Tous les flux de l'application web doivent être chiffrés, notamment avec **HTTPS/TLS** pour les échanges web.

La solution prévoit également :

- la mise en place d'une **PKI** pour signer les certificats X.509 ;
- le hachage sécurisé des mots de passe ;
- le renouvellement régulier des secrets liés aux comptes ;
- le stockage côté serveur des jetons de session et autres secrets sensibles.

### 2.4 Administration de l'application web

Les opérations suivantes sont accessibles uniquement depuis un portail administrateur :

- créer un compte ;
- modifier un compte ;
- supprimer un compte.

L'accès à ce portail nécessite un compte préalablement authentifié et un jeton de session dédié aux fonctions d'administration.

### 2.5 Accès aux endpoints

La page d'accueil comporte un menu répertoriant les endpoints disponibles dans l'application web.

L'accès à chaque endpoint API est contrôlé par une **liste d'autorisation (whitelist)** :

- seuls les rôles et comptes explicitement autorisés peuvent y accéder ;
- toute autre tentative est refusée immédiatement ;
- le refus est enregistré dans les logs afin d'assurer la traçabilité.

## 3. Contraintes et précisions

### 3.1 Scalabilité et gestion de la fréquentation

La fréquentation du site est variable et peut fortement augmenter entre 8 h et 10 h, ainsi qu'à l'approche de l'échéance fiscale autour de la fin du mois de juin. Le trafic peut alors atteindre **20 millions d'utilisateurs**.

Pour absorber cette charge, l'architecture prévoit :

- une file d'attente pour réguler les connexions ;
- un répartiteur de charge (*load balancer*) ;
- une conception capable de monter en charge horizontalement.

### 3.2 Traçabilité et suivi

Une traçabilité complète de l'application doit faciliter le travail de l'équipe de surveillance et de réponse aux incidents.

**Chaque événement doit contenir au minimum :**

| Donnée | Description |
| --- | --- |
| Timestamp | Jour et heure au format universel |
| Compte | Utilisateur ou compte concerné |
| Action | Opération réalisée |
| Endpoint | Ressource sollicitée |
| Adresse IP | Adresse IP de l'utilisateur |

Les opérations à risque important ou critique disposent d'un niveau de priorité supérieur dans les logs : accès au panneau d'administration, réinitialisation d'un mot de passe, création ou suppression d'un compte.

### 3.3 Résistance aux injections

L'attaque précédente ayant entraîné une fuite de données, les champs des formulaires d'authentification doivent être particulièrement protégés.

Des validations, filtres et contrôles doivent prévenir les attaques suivantes :

- XSS (*Cross-Site Scripting*) ;
- injection SQL (SQLi) ;
- injection de commandes (*Command Injection*) ;
- autres attaques par injection identifiées lors des tests de sécurité.