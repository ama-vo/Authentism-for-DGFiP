// Onglet "Comptes" : créer, modifier les accès, changer le mot de passe, supprimer
//
// Rappel : un administrateur a DEUX mots de passe différents
//  - le mot de passe de connexion (portail) ;
//  - le mot de passe d'administration (panneau d'administration).
import { FormEvent, useEffect, useState } from "react";
import { api } from "../../api";
import { useAuth } from "../../AuthContext";
import { AccountUser, Role, ROLE_LABELS } from "../../types";
import PasswordRules, { isStrongPassword } from "../PasswordRules";
import { useAdminError } from "./useAdminError";

const ROLES = Object.keys(ROLE_LABELS) as Role[];
const EMPTY_FORM = {
  fiscalNumber: "", firstName: "", lastName: "", email: "",
  role: "usager" as Role, password: "", adminPassword: "",
};

export default function UsersTab() {
  const { user: me } = useAuth();
  const { error, setError, handleError } = useAdminError();
  const [users, setUsers] = useState<AccountUser[]>([]);
  const [success, setSuccess] = useState("");

  // Création de compte
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  // Changement de mot de passe d'un compte
  const [passwordFor, setPasswordFor] = useState<AccountUser | null>(null);
  const [passwordTarget, setPasswordTarget] = useState<"login" | "admin">("login");
  const [newPassword, setNewPassword] = useState("");

  // Promotion en administrateur (demande le mot de passe d'administration)
  const [promote, setPromote] = useState<AccountUser | null>(null);
  const [promotePassword, setPromotePassword] = useState("");

  async function load() {
    try {
      const data = await api<{ users: AccountUser[] }>("/admin/users");
      setUsers(data.users);
    } catch (err) {
      handleError(err);
    }
  }

  useEffect(() => {
    load();
  }, []);

  // Exécute une action, affiche le résultat puis recharge la liste
  async function run(action: () => Promise<unknown>, message: string) {
    setError("");
    setSuccess("");
    try {
      await action();
      setSuccess(message);
      await load();
    } catch (err) {
      handleError(err);
    }
  }

  function createUser(e: FormEvent) {
    e.preventDefault();
    const { adminPassword, ...rest } = form;
    const body = form.role === "admin" ? form : rest; // mot de passe admin envoyé seulement pour un admin
    run(async () => {
      await api("/admin/users", "POST", body);
      setForm(EMPTY_FORM);
      setShowCreate(false);
    }, "Compte créé");
  }

  function changeRole(u: AccountUser, role: Role) {
    // Devenir admin demande de définir un mot de passe d'administration
    if (role === "admin") {
      setPromote(u);
      setPromotePassword("");
      return;
    }
    run(() => api(`/admin/users/${u.fiscalNumber}/role`, "PATCH", { role }), `Rôle de ${u.firstName} ${u.lastName} modifié`);
  }

  function confirmPromotion(e: FormEvent) {
    e.preventDefault();
    if (!promote) return;
    run(async () => {
      await api(`/admin/users/${promote.fiscalNumber}/role`, "PATCH", { role: "admin", adminPassword: promotePassword });
      setPromote(null);
    }, `${promote.firstName} ${promote.lastName} est maintenant administrateur`);
  }

  function openPasswordForm(u: AccountUser) {
    setPasswordFor(u);
    setPasswordTarget("login");
    setNewPassword("");
  }

  function changePassword(e: FormEvent) {
    e.preventDefault();
    if (!passwordFor) return;
    run(async () => {
      await api(`/admin/users/${passwordFor.fiscalNumber}/password`, "PUT", { password: newPassword, target: passwordTarget });
      setPasswordFor(null);
      setNewPassword("");
    }, "Mot de passe modifié, les sessions de l'utilisateur ont été fermées");
  }

  function remove(u: AccountUser) {
    if (!window.confirm(`Supprimer définitivement le compte de ${u.firstName} ${u.lastName} ?`)) return;
    run(() => api(`/admin/users/${u.fiscalNumber}`, "DELETE"), "Compte supprimé");
  }

  const update = (field: keyof typeof EMPTY_FORM, value: string) => setForm({ ...form, [field]: value });

  const createValid =
    isStrongPassword(form.password) &&
    (form.role !== "admin" || (isStrongPassword(form.adminPassword) && form.adminPassword !== form.password));

  return (
    <>
      {error && <p className="alert error">{error}</p>}
      {success && <p className="alert success">{success}</p>}

      <button className="btn" onClick={() => setShowCreate(!showCreate)}>
        {showCreate ? "Annuler" : "+ Créer un compte"}
      </button>

      {showCreate && (
        <form className="card form-grid" onSubmit={createUser}>
          <div>
            <label>Numéro fiscal</label>
            <input inputMode="numeric" maxLength={13} value={form.fiscalNumber}
              onChange={(e) => update("fiscalNumber", e.target.value.replace(/\D/g, ""))} required />
          </div>
          <div>
            <label>Rôle</label>
            <select value={form.role} onChange={(e) => update("role", e.target.value)}>
              {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
            </select>
          </div>
          <div>
            <label>Prénom</label>
            <input maxLength={50} value={form.firstName} onChange={(e) => update("firstName", e.target.value)} required />
          </div>
          <div>
            <label>Nom</label>
            <input maxLength={50} value={form.lastName} onChange={(e) => update("lastName", e.target.value)} required />
          </div>
          <div>
            <label>E-mail (reçoit les codes de connexion)</label>
            <input type="email" maxLength={100} value={form.email} onChange={(e) => update("email", e.target.value)} required />
          </div>
          <div>
            <label>Mot de passe de connexion (provisoire)</label>
            <input type="password" autoComplete="new-password" maxLength={128} value={form.password}
              onChange={(e) => update("password", e.target.value)} required />
            <PasswordRules password={form.password} />
          </div>
          {form.role === "admin" && (
            <div>
              <label>Mot de passe d'administration</label>
              <input type="password" autoComplete="new-password" maxLength={128} value={form.adminPassword}
                onChange={(e) => update("adminPassword", e.target.value)} required />
              <PasswordRules password={form.adminPassword} />
              {form.adminPassword && form.adminPassword === form.password && (
                <p className="alert error">Il doit être différent du mot de passe de connexion.</p>
              )}
            </div>
          )}
          <button className="btn" disabled={!createValid}>Créer le compte</button>
        </form>
      )}

      {promote && (
        <form className="card" onSubmit={confirmPromotion}>
          <h3>Passer {promote.firstName} {promote.lastName} administrateur</h3>
          <p className="alert info">
            Choisissez son mot de passe d'administration. Il doit être différent de son mot de passe de connexion.
          </p>
          <input type="password" autoComplete="new-password" maxLength={128} value={promotePassword}
            onChange={(e) => setPromotePassword(e.target.value)} required autoFocus />
          <PasswordRules password={promotePassword} />
          <button className="btn" disabled={!isStrongPassword(promotePassword)}>Confirmer</button>{" "}
          <button type="button" className="btn btn-secondary" onClick={() => setPromote(null)}>Annuler</button>
        </form>
      )}

      {passwordFor && (
        <form className="card" onSubmit={changePassword}>
          <h3>Nouveau mot de passe pour {passwordFor.firstName} {passwordFor.lastName}</h3>
          {passwordFor.role === "admin" && (
            <>
              <label>Mot de passe à modifier</label>
              <select value={passwordTarget} onChange={(e) => setPasswordTarget(e.target.value as "login" | "admin")}>
                <option value="login">Mot de passe de connexion</option>
                <option value="admin">Mot de passe d'administration</option>
              </select>
            </>
          )}
          <label>Nouveau mot de passe</label>
          <input type="password" autoComplete="new-password" maxLength={128} value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)} required autoFocus />
          <PasswordRules password={newPassword} />
          <button className="btn" disabled={!isStrongPassword(newPassword)}>Enregistrer</button>{" "}
          <button type="button" className="btn btn-secondary" onClick={() => setPasswordFor(null)}>Annuler</button>
        </form>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Numéro fiscal</th><th>Nom</th><th>E-mail</th><th>Rôle</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {users.map((u) => {
              const isMe = u.fiscalNumber === me?.fiscalNumber;
              return (
                <tr key={u.fiscalNumber}>
                  <td>{u.fiscalNumber}</td>
                  <td>{u.firstName} {u.lastName} {isMe && <em>(vous)</em>}</td>
                  <td>{u.email}</td>
                  <td>
                    <select value={u.role} disabled={isMe} onChange={(e) => changeRole(u, e.target.value as Role)}>
                      {ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                    </select>
                  </td>
                  <td className="actions">
                    <button className="btn-link" onClick={() => openPasswordForm(u)}>Mot de passe</button>
                    {!isMe && <button className="btn-link danger" onClick={() => remove(u)}>Supprimer</button>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
