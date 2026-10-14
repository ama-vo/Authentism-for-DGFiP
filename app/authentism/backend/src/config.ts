// Toute la configuration de l'API, lue depuis les variables d'environnement
// (définies dans docker-compose.yml et le fichier .env).

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    console.error(`[config] Variable d'environnement manquante : ${name}`);
    console.error("[config] Vérifiez le fichier .env puis relancez avec : docker compose up --build");
    process.exit(1);
  }
  return value;
}

export const config = {
  port: 3000,
  publicUrl: process.env.PUBLIC_URL || "https://localhost",

  // Annuaire LDAP existant (voir le fichier .env)
  ldap: {
    url: required("LDAP_URL"), // ldaps://serveur:636 (chiffré) recommandé
    bindDn: required("LDAP_BIND_DN"), // compte de service de l'application
    bindPassword: required("LDAP_BIND_PASSWORD"),
    usersDn: required("LDAP_USERS_DN"), // branche où se trouvent les comptes
    loginAttribute: process.env.LDAP_LOGIN_ATTRIBUTE || "uid", // contient le numéro fiscal
    roleAttribute: process.env.LDAP_ROLE_ATTRIBUTE || "employeeType", // usager | agent | admin
    caFile: "/ldap-ca/ca.crt", // facultatif : CA du serveur LDAP
  },

  redisUrl: required("REDIS_URL"),
  databaseUrl: required("DATABASE_URL"),

  smtp: {
    host: required("SMTP_HOST"),
    port: Number(process.env.SMTP_PORT || 1025),
    from: "DGFiP - Ne pas répondre <no-reply@dgfip.local>",
  },

  // Durées de vie (en secondes)
  sessionTtl: 30 * 60, // session utilisateur : 30 min d'inactivité
  adminSessionTtl: 15 * 60, // session administrateur : 15 min
  mfaTtl: 5 * 60, // code MFA valable 5 min
  resetTtl: 15 * 60, // lien de réinitialisation valable 15 min

  // Sécurité
  maxLoginFailures: 5, // blocage du compte après 5 échecs
  lockDuration: 15 * 60, // pendant 15 min
  maxMfaAttempts: 3,
  passwordMaxAgeDays: 90, // renouvellement obligatoire du mot de passe
};
