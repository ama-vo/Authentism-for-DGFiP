import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { Account, LogEntry, Role } from "../types";
import { isFiscalIdValid, isPasswordValid } from "../utils/validation";

const ROLE_LABELS: Record<Role, string> = {
  external: "Utilisateur externe",
  agent: "Agent DGFiP",
  admin: "Administrateur système",
};

export function AdminPage() {
  const { adminToken } = useAuth();
  const [tab, setTab] = useState<"accounts" | "logs">("accounts");
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [message, setMessage] = useState<{ text: string; kind: "success" | "error" } | null>(null);

  const [newFiscalId, setNewFiscalId] = useState("");
  const [newName, setNewName] = useState("");
  const [newRole, setNewRole] = useState<Role>("external");
  const [newPassword, setNewPassword] = useState("");

  async function refreshAccounts() {
    if (!adminToken) return;
    try {
      setAccounts(await api.listAccounts(adminToken));
    } catch (err) {
      flash(err instanceof ApiError ? err.message : "Erreur de chargement des comptes.", "error");
    }
  }

  async function refreshLogs() {
    if (!adminToken) return;
    try {
      setLogs(await api.listLogs(adminToken));
    } catch (err) {
      flash(err instanceof ApiError ? err.message : "Erreur de chargement du journal.", "error");
    }
  }

  useEffect(() => {
    refreshAccounts();
    refreshLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [adminToken]);

  function flash(text: string, kind: "success" | "error") {
    setMessage({ text, kind });
    setTimeout(() => setMessage(null), 3200);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!adminToken) return;

    if (!isFiscalIdValid(newFiscalId)) {
      flash("Numéro fiscal invalide (13 chiffres requis).", "error");
      return;
    }
    if (!newName.trim()) {
      flash("Le nom est obligatoire.", "error");
      return;
    }
    if (!isPasswordValid(newPassword)) {
      flash("Le mot de passe initial ne respecte pas la politique de sécurité.", "error");
      return;
    }

    try {
      await api.createAccount(adminToken, {
        fiscal_id: newFiscalId,
        name: newName.trim(),
        role: newRole,
        password: newPassword,
      });
      setNewFiscalId("");
      setNewName("");
      setNewPassword("");
      setNewRole("external");
      flash("Compte créé avec succès.", "success");
      refreshAccounts();
      refreshLogs();
    } catch (err) {
      flash(err instanceof ApiError ? err.message : "Impossible de créer le compte.", "error");
    }
  }

  async function handleDelete(account: Account) {
    if (!adminToken) return;
    if (!confirm(`Supprimer le compte ${account.fiscal_id} ?`)) return;
    try {
      await api.deleteAccount(adminToken, account.id);
      flash("Compte supprimé.", "success");
      refreshAccounts();
      refreshLogs();
    } catch (err) {
      flash(err instanceof ApiError ? err.message : "Impossible de supprimer le compte.", "error");
    }
  }

  async function handleRoleChange(account: Account, role: Role) {
    if (!adminToken) return;
    try {
      await api.updateAccount(adminToken, account.id, { role });
      flash("Compte mis à jour.", "success");
      refreshAccounts();
      refreshLogs();
    } catch (err) {
      flash(err instanceof ApiError ? err.message : "Impossible de modifier le compte.", "error");
    }
  }

  return (
    <div>
      <div className="portal-head">
        <h1>Panneau d'administration</h1>
        <p>Gestion des comptes et journal de traçabilité — jeton d'administration actif.</p>
      </div>

      <div className="admin-tabs">
        <button className={`admin-tab ${tab === "accounts" ? "active" : ""}`} onClick={() => setTab("accounts")}>
          Comptes
        </button>
        <button className={`admin-tab ${tab === "logs" ? "active" : ""}`} onClick={() => setTab("logs")}>
          Journal de traçabilité
        </button>
      </div>

      {message && <div className={`alert ${message.kind === "error" ? "error" : "success"}`}>{message.text}</div>}

      {tab === "accounts" && (
        <>
          <div className="panel">
            <div className="panel-head">
              <h2>Créer un compte</h2>
            </div>
            <form className="inline-form" onSubmit={handleCreate} noValidate>
              <div className="field">
                <label>Numéro fiscal</label>
                <input
                  value={newFiscalId}
                  onChange={(e) => setNewFiscalId(e.target.value.replace(/\D/g, "").slice(0, 13))}
                  maxLength={13}
                  placeholder="13 chiffres"
                />
              </div>
              <div className="field">
                <label>Nom</label>
                <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Nom complet" />
              </div>
              <div className="field">
                <label>Mot de passe initial</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Mot de passe temporaire"
                />
              </div>
              <div className="field">
                <label>Rôle</label>
                <select value={newRole} onChange={(e) => setNewRole(e.target.value as Role)}>
                  <option value="external">Utilisateur externe</option>
                  <option value="agent">Agent DGFiP</option>
                  <option value="admin">Administrateur système</option>
                </select>
              </div>
              <button type="submit" className="btn-small">
                Créer
              </button>
            </form>
          </div>

          <div className="panel">
            <div className="panel-head">
              <h2>Comptes existants</h2>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Numéro fiscal</th>
                    <th>Nom</th>
                    <th>Rôle</th>
                    <th>Créé le</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((acc) => (
                    <tr key={acc.id}>
                      <td className="mono">{acc.fiscal_id}</td>
                      <td>{acc.name}</td>
                      <td>
                        <select value={acc.role} onChange={(e) => handleRoleChange(acc, e.target.value as Role)}>
                          {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
                            <option key={r} value={r}>
                              {ROLE_LABELS[r]}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="mono">{acc.created_at.slice(0, 10)}</td>
                      <td>
                        <button className="btn-ghost danger" onClick={() => handleDelete(acc)}>
                          Supprimer
                        </button>
                      </td>
                    </tr>
                  ))}
                  {accounts.length === 0 && (
                    <tr>
                      <td colSpan={5} className="empty-state">
                        Aucun compte enregistré.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {tab === "logs" && (
        <div className="panel">
          <div className="panel-head">
            <h2>Journal des événements</h2>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Horodatage (UTC)</th>
                  <th>Compte</th>
                  <th>Action</th>
                  <th>Endpoint</th>
                  <th>Adresse IP</th>
                  <th>Priorité</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id}>
                    <td className="mono">{l.timestamp}</td>
                    <td className="mono">{l.account}</td>
                    <td>{l.action}</td>
                    <td className="mono">{l.endpoint}</td>
                    <td className="mono">{l.ip_address}</td>
                    <td>
                      <span className={`badge prio-${l.priority}`}>
                        {l.priority === "high" ? "Élevée" : "Normale"}
                      </span>
                    </td>
                  </tr>
                ))}
                {logs.length === 0 && (
                  <tr>
                    <td colSpan={6} className="empty-state">
                      Aucun événement enregistré.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
