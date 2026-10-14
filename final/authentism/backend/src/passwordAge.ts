// Date du dernier changement de mot de passe, stockée dans PostgreSQL.
// Sert à imposer le renouvellement régulier du mot de passe (90 jours),
// sans dépendre du schéma de l'annuaire LDAP existant.
import { db } from "./services";

// Nombre de jours depuis le dernier changement (null si jamais enregistré)
export async function passwordAgeDays(fiscalNumber: string): Promise<number | null> {
  const result = await db.query(
    "SELECT EXTRACT(DAY FROM now() - changed_at)::int AS days FROM password_changes WHERE fiscal_number = $1",
    [fiscalNumber]
  );
  return result.rowCount ? result.rows[0].days : null;
}

export async function markPasswordChanged(fiscalNumber: string) {
  await db.query(
    `INSERT INTO password_changes (fiscal_number, changed_at) VALUES ($1, now())
     ON CONFLICT (fiscal_number) DO UPDATE SET changed_at = now()`,
    [fiscalNumber]
  );
}
