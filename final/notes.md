faire des token statefull qui fait un token stateless qui a une duree de vie de 30s par ex (1 requete par sec par utt surcharge moins bd)

Les sessions sont stateful, mais l’API elle-même est sans état : aucune donnée n’est gardée dans la mémoire d’un réplica, tout est dans Redis. N’importe quel réplica peut donc traiter n’importe quelle requête. C’est ce qui permet de faire la montée en charge horizontale (--scale backend=N) et le SSO entre les services.

device session bound credentials
