// Fonctions d'administration (rôle admin + jeton d'administration, cf. whitelist.ts)
import { Router } from "express";
import { db } from "../services";
import { audit } from "../audit";
import { schemas, validate, fiscalNumber } from "../validation";
import { listUsers, findUser, createUser, updateRole, updatePassword, deleteUser } from "../ldap";
import { destroyAllSessions } from "../session";
import { markPasswordChanged } from "../passwordAge";

const router = Router();

// ===================== Comptes =====================

router.get("/users", async (_req, res) => {
  const users = await listUsers();
  // On ne renvoie que les informations utiles à l'affichage (pas le DN interne)
  res.json({
    users: users
      .map(({ dn, ...user }) => user)
      .sort((a, b) => a.fiscalNumber.localeCompare(b.fiscalNumber)),
  });
});

router.post("/users", async (req, res) => {
  const { data, error } = validate(schemas.createUser, req.body);
  if (!data) return res.status(400).json({ error });

  if (await findUser(data.fiscalNumber)) {
    return res.status(409).json({ error: "Un compte existe déjà avec ce numéro fiscal" });
  }
  await createUser(data);
  await markPasswordChanged(data.fiscalNumber);
  await audit(req, "USER_CREATE", true, undefined, `Compte ${data.fiscalNumber} (${data.role})`);
  res.status(201).json({ ok: true });
});

// Récupère et valide le numéro fiscal présent dans l'URL, et vérifie que le compte existe
async function targetUser(id: string) {
  const { data } = validate(fiscalNumber, id);
  return data ? findUser(data) : null;
}

router.patch("/users/:id/role", async (req, res) => {
  const user = await targetUser(req.params.id);
  if (!user) return res.status(404).json({ error: "Compte introuvable" });
  const { data, error } = validate(schemas.updateRole, req.body);
  if (!data) return res.status(400).json({ error });

  if (user.fiscalNumber === req.session!.fiscalNumber) {
    return res.status(400).json({ error: "Vous ne pouvez pas modifier votre propre rôle" });
  }
  await updateRole(user, data.role);
  await destroyAllSessions(user.fiscalNumber); // le nouveau rôle s'applique dès la prochaine connexion
  await audit(req, "USER_ROLE_UPDATE", true, undefined, `Compte ${user.fiscalNumber} : ${user.role} -> ${data.role}`);
  res.json({ ok: true });
});

router.put("/users/:id/password", async (req, res) => {
  const user = await targetUser(req.params.id);
  if (!user) return res.status(404).json({ error: "Compte introuvable" });
  const { data, error } = validate(schemas.updatePassword, req.body);
  if (!data) return res.status(400).json({ error });

  await updatePassword(user, data.password);
  await markPasswordChanged(user.fiscalNumber);
  await destroyAllSessions(user.fiscalNumber);
  await audit(req, "USER_PASSWORD_UPDATE", true, undefined, `Compte ${user.fiscalNumber}`);
  res.json({ ok: true });
});

router.delete("/users/:id", async (req, res) => {
  const user = await targetUser(req.params.id);
  if (!user) return res.status(404).json({ error: "Compte introuvable" });

  if (user.fiscalNumber === req.session!.fiscalNumber) {
    return res.status(400).json({ error: "Vous ne pouvez pas supprimer votre propre compte" });
  }
  await deleteUser(user);
  await destroyAllSessions(user.fiscalNumber);
  await audit(req, "USER_DELETE", true, undefined, `Compte ${user.fiscalNumber}`);
  res.json({ ok: true });
});

// ===================== Pages du dashboard =====================

router.get("/pages", async (_req, res) => {
  const result = await db.query("SELECT * FROM pages ORDER BY position");
  res.json({ pages: result.rows });
});

router.put("/pages/:slug", async (req, res) => {
  const { data: slug } = validate(schemas.slug, req.params.slug);
  const { data, error } = validate(schemas.page, req.body);
  if (!slug) return res.status(404).json({ error: "Page introuvable" });
  if (!data) return res.status(400).json({ error });

  const result = await db.query(
    "UPDATE pages SET title = $1, description = $2, content = $3, visible = $4 WHERE slug = $5",
    [data.title, data.description, data.content, data.visible, slug]
  );
  if (result.rowCount === 0) return res.status(404).json({ error: "Page introuvable" });

  await audit(req, "PAGE_UPDATE", true, undefined, `Page ${slug} (visible : ${data.visible})`);
  res.json({ ok: true });
});

// ===================== Journaux =====================

router.get("/logs", async (req, res) => {
  const priority = String(req.query.priority || "");
  // Filtre facultatif, uniquement parmi les valeurs autorisées
  const filter = ["INFO", "ELEVE", "CRITIQUE"].includes(priority) ? priority : null;

  const result = await db.query(
    `SELECT * FROM audit_logs
     WHERE ($1::text IS NULL OR priority = $1)
     ORDER BY timestamp DESC LIMIT 200`,
    [filter]
  );
  res.json({ logs: result.rows });
});

export default router;
