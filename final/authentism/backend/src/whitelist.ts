// =============================================================
//  LISTE D'AUTORISATION (whitelist) des endpoints de l'API
//
//  C'est LE fichier à lire pour comprendre qui a le droit de faire quoi.
//  Il reprend le tableau des permissions RBAC :
//  - un endpoint absent de cette liste est refusé pour tout le monde ;
//  - un rôle absent de "roles" est refusé ;
//  - "admin: true" exige en plus le jeton de session d'administration ;
//  - chaque refus est enregistré dans le journal d'audit.
// =============================================================
import { Request, Response, NextFunction } from "express";
import { Role } from "./ldap";
import { audit } from "./audit";
import { getSession, COOKIE_USER, COOKIE_ADMIN } from "./session";

const EVERYONE: Role[] = ["usager", "agent", "admin"];

interface Rule {
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  path: string; // ":param" = n'importe quelle valeur pour ce segment
  roles: Role[] | "public";
  admin?: boolean;
}

export const WHITELIST: Rule[] = [
  // --- Page d'authentification (accessible sans être connecté) ---
  { method: "GET", path: "/api/health", roles: "public" },
  { method: "GET", path: "/api/auth/me", roles: "public" }, // renvoie null si non connecté
  { method: "POST", path: "/api/auth/login", roles: "public" },
  { method: "POST", path: "/api/auth/mfa", roles: "public" },
  { method: "POST", path: "/api/auth/forgot-password", roles: "public" },
  { method: "POST", path: "/api/auth/reset-password", roles: "public" },

  // --- Dashboard et pages standard (tous les rôles connectés) ---
  { method: "POST", path: "/api/auth/logout", roles: EVERYONE },
  { method: "GET", path: "/api/pages", roles: EVERYONE },
  { method: "GET", path: "/api/pages/:slug", roles: EVERYONE },

  // --- Demande du jeton d'administration (admin connecté, mot de passe redemandé) ---
  { method: "POST", path: "/api/auth/admin-session", roles: ["admin"] },

  // --- Pages d'administration (admin + jeton d'administration) ---
  { method: "GET", path: "/api/admin/users", roles: ["admin"], admin: true },
  { method: "POST", path: "/api/admin/users", roles: ["admin"], admin: true },
  { method: "PATCH", path: "/api/admin/users/:id/role", roles: ["admin"], admin: true },
  { method: "PUT", path: "/api/admin/users/:id/password", roles: ["admin"], admin: true },
  { method: "DELETE", path: "/api/admin/users/:id", roles: ["admin"], admin: true },
  { method: "GET", path: "/api/admin/pages", roles: ["admin"], admin: true },
  { method: "PUT", path: "/api/admin/pages/:slug", roles: ["admin"], admin: true },
  { method: "GET", path: "/api/admin/logs", roles: ["admin"], admin: true },
];

// Transforme "/api/pages/:slug" en expression régulière ^/api/pages/[^/]+$
function matches(rule: Rule, method: string, path: string): boolean {
  if (rule.method !== method) return false;
  const pattern = "^" + rule.path.replace(/:[a-z]+/g, "[^/]+") + "/?$";
  return new RegExp(pattern).test(path);
}

async function deny(req: Request, res: Response, status: number, reason: string, code?: string) {
  await audit(req, "ACCESS_DENIED", false, undefined, reason);
  res.status(status).json({ error: "Accès refusé", code });
}

// Middleware appliqué à TOUTES les requêtes de l'API
export async function checkWhitelist(req: Request, res: Response, next: NextFunction) {
  try {
    // 1. On charge les sessions à partir des cookies (s'ils existent)
    req.session = (await getSession(req.cookies?.[COOKIE_USER], "user")) || undefined;
    const adminSession = await getSession(req.cookies?.[COOKIE_ADMIN], "admin");
    // Le jeton admin doit appartenir à la même personne que la session principale
    if (adminSession && req.session && adminSession.fiscalNumber === req.session.fiscalNumber) {
      req.adminSession = adminSession;
    }

    // 2. On cherche l'endpoint dans la liste d'autorisation
    const path = req.path;
    const rule = WHITELIST.find((r) => matches(r, req.method, path));
    if (!rule) return deny(req, res, 403, "Endpoint absent de la liste d'autorisation");

    if (rule.roles === "public") return next();

    // 3. Connexion obligatoire
    if (!req.session) return deny(req, res, 401, "Non authentifié", "NOT_AUTHENTICATED");

    // 4. Le rôle doit être explicitement autorisé
    if (!rule.roles.includes(req.session.role)) {
      return deny(req, res, 403, `Rôle "${req.session.role}" non autorisé`);
    }

    // 5. Jeton d'administration obligatoire pour les fonctions d'administration
    if (rule.admin && !req.adminSession) {
      return deny(req, res, 403, "Jeton d'administration manquant ou expiré", "ADMIN_SESSION_REQUIRED");
    }

    next();
  } catch (err) {
    next(err);
  }
}
