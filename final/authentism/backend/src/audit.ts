// Journal d'audit : chaque événement est écrit dans PostgreSQL ET affiché
// sur la sortie standard au format JSON (visible avec `docker compose logs backend`).
import { Request } from "express";
import { db } from "./services";

export type Priority = "INFO" | "ELEVE" | "CRITIQUE";

// Opérations à risque important ou critique (cf. cahier des charges §3.2)
const PRIORITIES: Record<string, Priority> = {
  LOGIN_LOCKED: "ELEVE",
  PASSWORD_RESET_REQUEST: "ELEVE",
  PASSWORD_RESET: "ELEVE",
  ACCESS_DENIED: "ELEVE",
  ADMIN_ACCESS: "CRITIQUE",
  ADMIN_ACCESS_FAILED: "CRITIQUE",
  USER_CREATE: "CRITIQUE",
  USER_DELETE: "CRITIQUE",
  USER_ROLE_UPDATE: "CRITIQUE",
  USER_PASSWORD_UPDATE: "CRITIQUE",
  PAGE_UPDATE: "ELEVE",
};

export async function audit(
  req: Request,
  action: string,
  success: boolean,
  account?: string,
  details?: string
) {
  const event = {
    timestamp: new Date().toISOString(), // format universel (UTC)
    account: account || req.session?.fiscalNumber || "anonyme",
    action,
    endpoint: `${req.method} ${req.originalUrl.split("?")[0]}`,
    ip: req.ip || "inconnue",
    priority: PRIORITIES[action] || "INFO",
    success,
    details: details || null,
  };

  console.log(JSON.stringify({ type: "audit", ...event }));

  try {
    // Requête paramétrée ($1, $2...) : les valeurs ne sont jamais concaténées au SQL
    await db.query(
      `INSERT INTO audit_logs (timestamp, account, action, endpoint, ip, priority, success, details)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
      [event.timestamp, event.account, event.action, event.endpoint, event.ip, event.priority, event.success, event.details]
    );
  } catch (err) {
    console.error("Impossible d'écrire le journal d'audit :", err);
  }
}
