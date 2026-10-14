// Point d'entrée de l'API Authentism
import express, { Request, Response, NextFunction } from "express";
import helmet from "helmet";
import cookieParser from "cookie-parser";
import { config } from "./config";
import { checkWhitelist } from "./whitelist";
import { testLdapConnection } from "./ldap";
import { db, redis } from "./services";
import authRoutes from "./routes/auth";
import pageRoutes from "./routes/pages";
import adminRoutes from "./routes/admin";

const app = express();

app.set("trust proxy", 1); // l'API est derrière nginx : on récupère la vraie IP du client
app.disable("x-powered-by");
app.use(helmet()); // en-têtes de sécurité HTTP
app.use(express.json({ limit: "10kb" })); // corps de requête limité
app.use(cookieParser());

// Toutes les requêtes passent par la liste d'autorisation AVANT les routes
app.use(checkWhitelist);

app.get("/api/health", async (_req, res) => {
  await Promise.all([redis.ping(), db.query("SELECT 1")]);
  res.json({ status: "ok" });
});

app.use("/api/auth", authRoutes);
app.use("/api/pages", pageRoutes);
app.use("/api/admin", adminRoutes);

// Gestion des erreurs : on journalise le détail, mais on ne renvoie jamais
// de message technique au navigateur (pas de fuite d'information).
app.use((err: Error & { status?: number }, _req: Request, res: Response, _next: NextFunction) => {
  // Erreurs du client (JSON mal formé, corps trop gros...)
  if (err.status && err.status < 500) {
    return res.status(err.status).json({ error: "Requête invalide" });
  }
  console.error(JSON.stringify({ type: "error", message: err.message, timestamp: new Date().toISOString() }));
  res.status(500).json({ error: "Erreur interne, veuillez réessayer" });
});

app.listen(config.port, () => {
  console.log(`API Authentism démarrée sur le port ${config.port}`);
  testLdapConnection();
});
