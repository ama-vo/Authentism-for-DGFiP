// Pages standard du dashboard (accessibles à tous les utilisateurs connectés)
import { Router } from "express";
import { db } from "../services";
import { audit } from "../audit";
import { schemas, validate } from "../validation";

const router = Router();

// Menu du dashboard : uniquement les pages rendues visibles par l'administrateur
router.get("/", async (_req, res) => {
  const result = await db.query(
    "SELECT slug, title, description FROM pages WHERE visible = true ORDER BY position"
  );
  res.json({ pages: result.rows });
});

router.get("/:slug", async (req, res) => {
  const { data: slug } = validate(schemas.slug, req.params.slug);
  if (!slug) return res.status(404).json({ error: "Page introuvable" });

  const result = await db.query(
    "SELECT slug, title, description, content FROM pages WHERE slug = $1 AND visible = true",
    [slug]
  );
  if (result.rowCount === 0) return res.status(404).json({ error: "Page introuvable" });

  await audit(req, "PAGE_VIEW", true, undefined, slug);
  res.json({ page: result.rows[0] });
});

export default router;
