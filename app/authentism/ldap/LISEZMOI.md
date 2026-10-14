# Dossier ldap/

L'application se connecte à un **annuaire LDAP existant** (configuré dans `.env`).

- `ldap-test.ldif` : comptes du LDAP de test (mode test, `COMPOSE_PROFILES=test`).

- `ca.crt` (à ajouter si besoin) : certificat de l'autorité qui a signé le certificat de votre
  serveur LDAP. Nécessaire pour `ldaps://` avec un certificat interne/auto-signé.
- `exemple-comptes.ldif` : comptes de test facultatifs à importer dans votre annuaire.

Chaque compte doit avoir : l'objectClass `inetOrgPerson`, le numéro fiscal dans `uid`,
une adresse `mail` (pour le code MFA) et le rôle dans `employeeType`
(`usager`, `agent` ou `admin`). Sans rôle, un compte est traité comme `usager`.
