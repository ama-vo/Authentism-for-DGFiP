# Plan d'action

Le projet peut être réalisé selon les grandes phases suivantes. Chaque phase doit être validée avant de passer à la suivante.

## 1. Cadrage et analyse des besoins

**Objectif :** transformer le besoin de la DGFiP en exigences vérifiables.

**Sous-tâches :**

- recenser les utilisateurs, services, rôles et endpoints concernés ;
- préciser les règles de mot de passe, de MFA, de session et de SSO ;
- définir les exigences de disponibilité, de montée en charge et de journalisation ;
- identifier les risques et les exigences réglementaires ;
- compléter la date de rendu et les critères d'acceptation.

**Outils adaptés :** Markdown, Git/GitHub, Jira ou GitHub Issues, draw.io ou Mermaid.

## 2. Conception de l'architecture

**Objectif :** définir les composants et les flux de la solution.

**Sous-tâches :**

- concevoir le portail d'authentification et les services d'identité ;
- définir l'intégration LDAP et la matrice des permissions RBAC ;
- définir le format, le périmètre, la durée de vie et le renouvellement des jetons ;
- concevoir le SSO entre les applications ;
- prévoir le load balancer, la file d'attente et la montée en charge ;
- définir l'architecture des logs et de la supervision.

**Outils adaptés :** draw.io ou Mermaid, UML, PostgreSQL ou annuaire LDAP de test, Docker.

## 3. Développement du socle d'authentification

**Objectif :** implémenter le parcours sécurisé de connexion.

**Sous-tâches :**

- développer le portail login/mot de passe ;
- appliquer et tester la politique de mot de passe ;
- intégrer l'envoi et la vérification du code MFA ;
- créer, renouveler, révoquer et invalider les sessions ;
- intégrer LDAP et les contrôles RBAC ;
- stocker les mots de passe et secrets avec des mécanismes adaptés.

**Outils adaptés :** Visual Studio Code, framework backend retenu, Git, Docker Compose, bibliothèque cryptographique reconnue, serveur LDAP et MailHog.

## 4. Développement de l'administration et des API

**Objectif :** contrôler les comptes et les accès aux ressources.

**Sous-tâches :**

- développer le portail administrateur ;
- restreindre la gestion des comptes au rôle administrateur ;
- établir la whitelist des endpoints ;
- appliquer l'autorisation sur chaque endpoint ;
- refuser et journaliser les accès non autorisés ;
- afficher la liste des endpoints sans exposer d'informations sensibles.

**Outils adaptés :** framework web, Postman ou Insomnia, OpenAPI/Swagger, middleware d'autorisation, GitHub Actions.

## 5. Sécurisation de l'infrastructure

**Objectif :** protéger les flux, les certificats et les secrets.

**Sous-tâches :**

- activer HTTPS/TLS sur tous les flux ;
- créer une PKI de test et gérer les certificats X.509 ;
- configurer le renouvellement des certificats et des secrets ;
- vérifier le stockage serveur des jetons et secrets ;
- configurer le load balancer et la file d'attente ;
- limiter les accès réseau aux composants nécessaires.

**Outils adaptés :** OpenSSL, HashiCorp Vault, Docker, Nginx ou Traefik, SSL Labs en environnement autorisé, Prometheus et Grafana.

## 6. Journalisation et supervision

**Objectif :** rendre les événements exploitables par l'équipe de surveillance.

**Sous-tâches :**

- enregistrer le timestamp universel, le compte, l'action, l'endpoint et l'adresse IP ;
- distinguer les événements normaux des événements critiques ;
- protéger les logs contre la modification et l'accès non autorisé ;
- centraliser les logs et définir leur durée de conservation ;
- créer des alertes pour les tentatives répétées et les actions sensibles.

**Outils adaptés :** ELK/Elastic Stack ou Graylog, Wazuh ou SIEM équivalent, Prometheus/Grafana.

## 7. Tests et validation de sécurité

**Objectif :** vérifier les exigences fonctionnelles, de sécurité et de performance.

**Sous-tâches :**

- écrire des tests unitaires et d'intégration pour l'authentification, le MFA, le SSO et le RBAC ;
- tester les accès autorisés et refusés sur chaque endpoint ;
- vérifier les protections contre XSS, SQLi et Command Injection ;
- tester l'expiration, la révocation et le renouvellement des sessions ;
- réaliser des tests de charge jusqu'au volume cible ;
- effectuer une revue de configuration et une analyse de vulnérabilités ;
- corriger les anomalies et rédiger le rapport de validation.

**Outils adaptés :** pytest ou équivalent, Postman/Newman, OWASP ZAP, Semgrep, Trivy, k6 ou JMeter, GitHub Actions.

## 8. Documentation et livraison

**Objectif :** rendre la solution compréhensible, déployable et maintenable.

**Sous-tâches :**

- documenter l'architecture, les flux et les choix de sécurité ;
- rédiger les procédures d'installation, de déploiement et de reprise ;
- documenter les rôles, endpoints, logs et procédures d'administration ;
- préparer une démonstration et une checklist de recette ;
- vérifier que les critères d'acceptation sont couverts.

**Outils adaptés :** Markdown, Mermaid/draw.io, OpenAPI/Swagger, MkDocs ou GitHub Pages, GitHub Releases.