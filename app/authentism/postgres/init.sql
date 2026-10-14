-- =============================================================
--  Base PostgreSQL : journaux d'audit + pages du dashboard
--  (les identités sont dans l'annuaire LDAP, pas ici)
-- =============================================================

-- Journal d'audit : un événement = une ligne
CREATE TABLE audit_logs (
  id          BIGSERIAL PRIMARY KEY,
  timestamp   TIMESTAMPTZ NOT NULL DEFAULT now(),  -- stocké en UTC
  account     TEXT        NOT NULL,                -- numéro fiscal ou "anonyme"
  action      TEXT        NOT NULL,                -- ex : LOGIN_SUCCESS
  endpoint    TEXT        NOT NULL,                -- ex : POST /api/auth/login
  ip          TEXT        NOT NULL,
  priority    TEXT        NOT NULL CHECK (priority IN ('INFO', 'ELEVE', 'CRITIQUE')),
  success     BOOLEAN     NOT NULL,
  details     TEXT
);
CREATE INDEX idx_audit_timestamp ON audit_logs (timestamp DESC);
CREATE INDEX idx_audit_priority  ON audit_logs (priority);

-- Pages affichées dans le menu du dashboard (modifiables par l'admin)
CREATE TABLE pages (
  slug        TEXT PRIMARY KEY,
  title       TEXT    NOT NULL,
  description TEXT    NOT NULL,
  content     TEXT    NOT NULL,
  visible     BOOLEAN NOT NULL DEFAULT true,
  position    INT     NOT NULL DEFAULT 0
);

INSERT INTO pages (slug, title, description, content, position) VALUES
  ('declaration', 'Déclarer mes revenus',
   'Accéder à la déclaration en ligne.',
   'La campagne de déclaration des revenus est ouverte. Pensez à vérifier vos informations avant la date limite de fin juin.', 1),
  ('documents', 'Mes documents',
   'Consulter vos avis d''imposition et justificatifs.',
   'Retrouvez ici vos avis d''impôt sur le revenu, de taxe foncière et vos accusés de réception.', 2),
  ('paiements', 'Mes paiements',
   'Gérer vos prélèvements et paiements en ligne.',
   'Consultez vos échéanciers, modifiez vos coordonnées bancaires et réglez vos impôts en ligne.', 3),
  ('messagerie', 'Messagerie sécurisée',
   'Échanger avec votre centre des finances publiques.',
   'Vous n''avez aucun nouveau message. Vos échanges avec l''administration apparaîtront ici.', 4);

-- Date du dernier changement de mot de passe (renouvellement obligatoire tous les 90 jours)
CREATE TABLE password_changes (
  fiscal_number TEXT PRIMARY KEY,
  changed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
