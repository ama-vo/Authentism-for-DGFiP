// Routes d'authentification : connexion + MFA, déconnexion, mot de passe oublié,
// et obtention du jeton d'administration.
import { Router, Request } from "express";
import crypto from "crypto";
import { config } from "../config";
import { redis, sendMail } from "../services";
import { audit } from "../audit";
import { schemas, validate } from "../validation";
import { findUser, checkPassword, updatePassword } from "../ldap";
import { passwordAgeDays, markPasswordChanged } from "../passwordAge";
import {
  createSession, destroySession, destroyAllSessions, randomToken,
  cookieOptions, COOKIE_USER, COOKIE_ADMIN,
} from "../session";

const router = Router();

const sha256 = (value: string) => crypto.createHash("sha256").update(value).digest("hex");
const GENERIC_ERROR = "Numéro fiscal ou mot de passe incorrect";


// a****@dgfip.local : on montre à l'utilisateur où le code est parti sans tout dévoiler
function maskEmail(email: string) {
  const [name, domain] = email.split("@");
  return `${name[0]}****@${domain}`;
}

// ---------------------------------------------------------------
// Étape 1 : numéro fiscal + mot de passe  ->  envoi du code MFA par e-mail
// ---------------------------------------------------------------
router.post("/login", async (req, res) => {
  const { data, error } = validate(schemas.login, req.body);
  if (!data) return res.status(400).json({ error });

  // Blocage temporaire après trop d'échecs (protection contre la force brute)
  const failKey = `fails:${data.fiscalNumber}`;
  const fails = Number((await redis.get(failKey)) || 0);
  if (fails >= config.maxLoginFailures) {
    await audit(req, "LOGIN_LOCKED", false, data.fiscalNumber);
    return res.status(429).json({ error: "Compte temporairement bloqué suite à trop d'échecs. Réessayez dans 15 minutes." });
  }

  const user = await findUser(data.fiscalNumber);
  // Le mot de passe est vérifié par l'annuaire LDAP (bind avec le compte de l'utilisateur)
  const passwordOk = user ? await checkPassword(user, data.password) : false;

  if (!user || !passwordOk) {
    const count = await redis.incr(failKey);
    await redis.expire(failKey, config.lockDuration);
    await audit(req, count >= config.maxLoginFailures ? "LOGIN_LOCKED" : "LOGIN_FAILED", false, data.fiscalNumber);
    return res.status(401).json({ error: GENERIC_ERROR });
  }

  // Renouvellement régulier du mot de passe (90 jours)
  const age = await passwordAgeDays(user.fiscalNumber);
  if (age === null) {
    await markPasswordChanged(user.fiscalNumber); // première connexion : on démarre le compteur
  } else if (age > config.passwordMaxAgeDays) {
    await audit(req, "PASSWORD_EXPIRED", false, user.fiscalNumber);
    return res.status(403).json({
      error: "Votre mot de passe a expiré. Utilisez « Mot de passe oublié » pour en définir un nouveau.",
    });
  }

  // Second facteur : code à 6 chiffres envoyé par e-mail (attribut "mail" de l'annuaire)
  if (!user.email) {
    await audit(req, "LOGIN_FAILED", false, user.fiscalNumber, "Aucune adresse e-mail pour le MFA");
    return res.status(403).json({ error: "Aucune adresse e-mail n'est associée à ce compte. Contactez un administrateur." });
  }
  const code = crypto.randomInt(0, 1_000_000).toString().padStart(6, "0");
  const challengeId = randomToken();
  await redis.set(
    `mfa:${challengeId}`,
    JSON.stringify({ fiscalNumber: user.fiscalNumber, codeHash: sha256(code), attempts: 0 }),
    "EX",
    config.mfaTtl
  );
  await sendMail(
    user.email,
    "Votre code de connexion DGFiP",
    `Bonjour ${user.firstName},\n\nVotre code de connexion est : ${code}\n\n` +
      `Il est valable 5 minutes. Si vous n'êtes pas à l'origine de cette demande, changez votre mot de passe.`
  );

  await audit(req, "LOGIN_PASSWORD_OK", true, user.fiscalNumber, "Code MFA envoyé");
  res.json({ challengeId, email: maskEmail(user.email) });
});

// ---------------------------------------------------------------
// Étape 2 : vérification du code MFA  ->  création de la session (SSO)
// ---------------------------------------------------------------
router.post("/mfa", async (req, res) => {
  const { data, error } = validate(schemas.mfa, req.body);
  if (!data) return res.status(400).json({ error });

  const key = `mfa:${data.challengeId}`;
  const raw = await redis.get(key);
  if (!raw) return res.status(401).json({ error: "Code expiré. Veuillez vous reconnecter." });

  const challenge = JSON.parse(raw) as { fiscalNumber: string; codeHash: string; attempts: number };
  const ok = crypto.timingSafeEqual(Buffer.from(sha256(data.code)), Buffer.from(challenge.codeHash));

  if (!ok) {
    challenge.attempts++;
    if (challenge.attempts >= config.maxMfaAttempts) {
      await redis.del(key); // trop d'essais : il faut recommencer depuis le début
    } else {
      await redis.set(key, JSON.stringify(challenge), "KEEPTTL");
    }
    await audit(req, "MFA_FAILED", false, challenge.fiscalNumber, `Essai ${challenge.attempts}`);
    return res.status(401).json({ error: "Code incorrect" });
  }

  await redis.del(key); // un code ne sert qu'une seule fois
  await redis.del(`fails:${challenge.fiscalNumber}`);

  const user = await findUser(challenge.fiscalNumber);
  if (!user) return res.status(401).json({ error: GENERIC_ERROR });

  const token = await createSession({
    fiscalNumber: user.fiscalNumber,
    name: `${user.firstName} ${user.lastName}`,
    role: user.role,
    scope: "user",
  });
  res.cookie(COOKIE_USER, token, cookieOptions);

  await audit(req, "LOGIN_SUCCESS", true, user.fiscalNumber);
  res.json({ ok: true });
});

// ---------------------------------------------------------------
// Utilisateur connecté (ou null)
// ---------------------------------------------------------------
router.get("/me", (req, res) => {
  if (!req.session) return res.json({ user: null });
  res.json({
    user: {
      fiscalNumber: req.session.fiscalNumber,
      name: req.session.name,
      role: req.session.role,
      hasAdminSession: Boolean(req.adminSession),
    },
  });
});

router.post("/logout", async (req: Request, res) => {
  await destroySession(req.cookies?.[COOKIE_USER]);
  await destroySession(req.cookies?.[COOKIE_ADMIN]);
  res.clearCookie(COOKIE_USER, cookieOptions);
  res.clearCookie(COOKIE_ADMIN, cookieOptions);
  await audit(req, "LOGOUT", true);
  res.json({ ok: true });
});

// ---------------------------------------------------------------
// Mot de passe oublié : envoi d'un lien à usage unique par e-mail
// ---------------------------------------------------------------
router.post("/forgot-password", async (req, res) => {
  const { data, error } = validate(schemas.forgot, req.body);
  if (!data) return res.status(400).json({ error });

  // Même réponse que le compte existe ou non (on ne révèle rien à un attaquant)
  const answer = { ok: true, message: "Si ce compte existe, un e-mail de réinitialisation a été envoyé." };

  const user = await findUser(data.fiscalNumber);
  // Anti-spam : une seule demande par minute et par compte
  const allowed = user && (await redis.set(`reset-cooldown:${user.fiscalNumber}`, "1", "EX", 60, "NX"));
  if (!user || !allowed) {
    await audit(req, "PASSWORD_RESET_REQUEST", false, data.fiscalNumber);
    return res.json(answer);
  }

  const token = randomToken();
  // On stocke seulement le hash du jeton : une fuite de Redis ne permet pas de l'utiliser
  await redis.set(`reset:${sha256(token)}`, user.fiscalNumber, "EX", config.resetTtl);
  await sendMail(
    user.email,
    "Réinitialisation de votre mot de passe DGFiP",
    `Bonjour ${user.firstName},\n\nPour choisir un nouveau mot de passe, ouvrez ce lien (valable 15 minutes) :\n` +
      `${config.publicUrl}/reinitialiser?token=${token}\n\nSi vous n'êtes pas à l'origine de cette demande, ignorez ce message.`
  );

  await audit(req, "PASSWORD_RESET_REQUEST", true, user.fiscalNumber);
  res.json(answer);
});

router.post("/reset-password", async (req, res) => {
  const { data, error } = validate(schemas.reset, req.body);
  if (!data) return res.status(400).json({ error });

  const key = `reset:${sha256(data.token)}`;
  const fiscalNumber = await redis.get(key);
  if (!fiscalNumber) {
    await audit(req, "PASSWORD_RESET", false, undefined, "Lien invalide ou expiré");
    return res.status(400).json({ error: "Lien invalide ou expiré" });
  }
  await redis.del(key); // lien à usage unique

  const user = await findUser(fiscalNumber);
  if (!user) return res.status(400).json({ error: "Lien invalide ou expiré" });

  await updatePassword(user, data.newPassword);
  await markPasswordChanged(fiscalNumber);
  await destroyAllSessions(fiscalNumber); // déconnecte toutes les sessions ouvertes
  await redis.del(`fails:${fiscalNumber}`);

  await sendMail(user.email, "Votre mot de passe DGFiP a été modifié",
    "Votre mot de passe vient d'être modifié. Si vous n'êtes pas à l'origine de ce changement, contactez immédiatement votre centre des finances publiques.");

  await audit(req, "PASSWORD_RESET", true, fiscalNumber);
  res.json({ ok: true });
});

// ---------------------------------------------------------------
// Jeton d'administration : l'admin déjà connecté redonne son mot de passe
// et reçoit un jeton dédié, de courte durée, limité aux fonctions d'administration.
// ---------------------------------------------------------------
router.post("/admin-session", async (req, res) => {
  const { data, error } = validate(schemas.adminSession, req.body);
  if (!data) return res.status(400).json({ error });

  const user = await findUser(req.session!.fiscalNumber);
  const ok = user && user.role === "admin" && (await checkPassword(user, data.password));
  if (!user || !ok) {
    await audit(req, "ADMIN_ACCESS_FAILED", false);
    return res.status(401).json({ error: "Mot de passe incorrect" });
  }

  await destroySession(req.cookies?.[COOKIE_ADMIN]);
  const token = await createSession({
    fiscalNumber: user.fiscalNumber,
    name: `${user.firstName} ${user.lastName}`,
    role: user.role,
    scope: "admin",
  });
  res.cookie(COOKIE_ADMIN, token, cookieOptions);

  await audit(req, "ADMIN_ACCESS", true);
  res.json({ ok: true });
});

export default router;
