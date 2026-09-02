=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
+                                                                                    |
| 1 - Introduction :                                                                 +
+                                                                                    |
=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+

Récemment victime d'une cyber-attaque de grande ampleur ayant pour origine son système d'authentification, la Direction Générale des Finances Publiques (DGFiP) a souhaité revoir son système de gestion des identités et accès. À ce titre, la DGFiP a mandaté la société Authentism, spécialiste des questions de sécurité des systèmes d'informations et de l'Identity and Acess Management (IAM).

=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
+                                                                                    |
| 2 - Proposition technique :                                                        +
+                                                                                    |
=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+

Afin de réaliser la transformation attendue par la DGFiP, Authentism a complètement redéfini l'architecture cible de la DGFiP en mettant la sécurité au coeur du projet. Pour pouvoir accéder aux services de la DGFiP, les utilisateurs auront a s'authentifier au travers d'un portail sur la base d'un combo login/mot de passe. Le login est le numéro fiscal de l'utilisateur et le mot de passe est défini en respectant les politiques définies par la DGFiP, telles qu'une longueur minimale de 12 caractères et obligation de contenir tous les types de caractères suivants : lettre majuscule, lettre minuscule, chiffre, caractère spécial. Une authentification multi-facteur sera également obligatoire au minimum pour les comptes des agents de la DGFiP et des administrateurs systèmes, via l'envoi d'un code sur l'adresse mail du compte essayant de se connecter.

Une fois authentifié, l'identité de l'utilisateur sera garantie par un jeton de session possédant un périmètre défini préalablement, afin de permettre l'implementation d'un Single Sign-On (SSO), garantissant une ergonomie aux différents utilisateurs. La gestion des identités sera traîtée grâce à un Lightweight Directory Access Protocol (LDAP) ainsi qu'un contrôle d'accès basé sur les différents rôles RBAC (utilisateur externe, agent de la DGFiP, administrateur système).

La sécurité étant la priorité du projet, l'intégralité des flux de l'application web seront chiffrés à l'aide de différents protocoles, HTTPs/TLS pour les flux web par exemple. Les mots de passe seront hashés et les secrets liés aux comptes tels que les jetons de session seront régulièrement renouvelés et stockés côté serveur.

La création, suppression et modification de comptes et de mots de passe ne pourra se faire que depuis un portail administrateur, nécessitant un compte identifié préalablement et possédant un jeton de session particulier. 

Tout accès à un endpoint API est contrôlé par une whitelist, les rôles/comptes renseignés étant les seuls autorisés, tout autre accès étant immédiatement refusé et renseigné dans des logs pour la traçabilité.

=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
+                                                                                    |
| 3 - Contraintes et précisions :                                                    +
+                                                                                    |
=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+

La fréquentation du site étant très variable et instable, il sera implémenté un système de gestion de la fréquentation avec une file d'attente et un load balancer afin de palier aux problèmes de surfréquentation lors des phases d'authentification entre 8h et 10h, ainsi qu'à l'approche de l'échéance fiscale autour de la fin du mois de juin.

Afin de faciliter le travail de l'équipe de surveillance et réponse aux incidents, une traçabilité totale de l'application sera mise en place contenant au minimum les informations suivantes : Jour et heure en utilisant un timestamp universel, compte, action performée, endpoint, IP de l'utilisateur. Les actions à risques importants/critiques tels l'accès au panel administrateur, la réinitialisation de mot de passe, la création ou suppression de comptes feront l'objet de création d'un fichier de log avec une priorité supplémentaire.

L'attaque précédente à l'encontre de la DGFiP ayant entraîné une fuite de données, l'accent sera donc mis sur la sécurisation des différents champs du formulaire d'authentification, en veillant à mettre en place des filtres et contrôles pour éviter les différentes attaques par injection (XSS, SQLi, Command Injection ...)
