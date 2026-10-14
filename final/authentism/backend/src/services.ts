// Connexions aux services externes : Redis, PostgreSQL et serveur mail.
import Redis from "ioredis";
import { Pool } from "pg";
import nodemailer from "nodemailer";
import { config } from "./config";

// Redis : sessions, codes MFA, compteurs d'échecs (partagés entre les réplicas de l'API)
export const redis = new Redis(config.redisUrl);
redis.on("error", (err) => console.error(`[redis] ${err.message}`)); // on log, sans arrêter l'API

// PostgreSQL : journaux d'audit et pages du dashboard
export const db = new Pool({ connectionString: config.databaseUrl, max: 10 });
db.on("error", (err) => console.error(`[postgres] ${err.message}`)); // idem

// Serveur SMTP : envoi des codes MFA et des liens de réinitialisation
const mailer = nodemailer.createTransport({
  host: config.smtp.host,
  port: config.smtp.port,
  secure: false,
});

export async function sendMail(to: string, subject: string, text: string) {
  await mailer.sendMail({ from: config.smtp.from, to, subject, text });
}
