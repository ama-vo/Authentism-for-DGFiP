// Gestion des jetons de session, stockés CÔTÉ SERVEUR dans Redis.
// Le navigateur ne reçoit qu'un identifiant aléatoire dans un cookie HttpOnly :
// aucune information sensible n'est stockée chez le client.
import crypto from "crypto";
import { redis } from "./services";
import { config } from "./config";
import { Role } from "./ldap";

// Périmètre du jeton, défini à l'avance :
//  - "user"  : accès au dashboard et aux pages standard (SSO entre les services)
//  - "admin" : accès aux fonctions d'administration (jeton dédié, durée courte)
export type Scope = "user" | "admin";

export interface Session {
  fiscalNumber: string;
  name: string;
  role: Role;
  scope: Scope;
  createdAt: string;
}

declare global {
  namespace Express {
    interface Request {
      session?: Session;
      adminSession?: Session;
    }
  }
}

export const COOKIE_USER = "session";
export const COOKIE_ADMIN = "admin_session";

export const randomToken = () => crypto.randomBytes(32).toString("hex"); // 64 caractères hex

const ttlOf = (scope: Scope) => (scope === "admin" ? config.adminSessionTtl : config.sessionTtl);

export async function createSession(data: Omit<Session, "createdAt">): Promise<string> {
  const token = randomToken();
  const session: Session = { ...data, createdAt: new Date().toISOString() };
  await redis.set(`session:${token}`, JSON.stringify(session), "EX", ttlOf(data.scope));
  // On garde la liste des sessions de chaque utilisateur pour pouvoir toutes les révoquer
  await redis.sadd(`user-sessions:${data.fiscalNumber}`, token);
  await redis.expire(`user-sessions:${data.fiscalNumber}`, 24 * 3600);
  return token;
}

// Lit une session et prolonge sa durée de vie (expiration après inactivité)
export async function getSession(token: string | undefined, scope: Scope): Promise<Session | null> {
  if (!token || !/^[a-f0-9]{64}$/.test(token)) return null;
  const raw = await redis.get(`session:${token}`);
  if (!raw) return null;
  const session = JSON.parse(raw) as Session;
  if (session.scope !== scope) return null; // un jeton "user" ne vaut pas un jeton "admin"
  await redis.expire(`session:${token}`, ttlOf(scope));
  return session;
}

export async function destroySession(token: string | undefined) {
  if (token) await redis.del(`session:${token}`);
}

// Révoque toutes les sessions d'un utilisateur (changement de mot de passe, suppression...)
export async function destroyAllSessions(fiscalNumber: string) {
  const key = `user-sessions:${fiscalNumber}`;
  const tokens = await redis.smembers(key);
  if (tokens.length) await redis.del(...tokens.map((t) => `session:${t}`));
  await redis.del(key);
}

// Options des cookies : inaccessibles en JavaScript (HttpOnly), HTTPS uniquement (Secure),
// jamais envoyés depuis un autre site (SameSite=Strict, protection CSRF)
export const cookieOptions = { httpOnly: true, secure: true, sameSite: "strict" as const, path: "/" };
