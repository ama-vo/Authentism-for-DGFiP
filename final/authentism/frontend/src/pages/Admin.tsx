// Portail d'administration.
// Pour y entrer, l'admin saisit son mot de passe D'ADMINISTRATION (différent de son
// mot de passe de connexion) et reçoit un jeton de session dédié, valable 15 minutes.
import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useAuth } from "../AuthContext";
import UsersTab from "../components/admin/UsersTab";
import PagesTab from "../components/admin/PagesTab";
import LogsTab from "../components/admin/LogsTab";

type Tab = "users" | "pages" | "logs";

export default function Admin() {
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>("users");

  if (!user?.hasAdminSession) return <AdminUnlock />;

  return (
    <>
      <p><Link to="/">← Retour au tableau de bord</Link></p>
      <h1>Administration</h1>

      <nav className="tabs">
        <button className={tab === "users" ? "active" : ""} onClick={() => setTab("users")}>Comptes</button>
        <button className={tab === "pages" ? "active" : ""} onClick={() => setTab("pages")}>Pages du dashboard</button>
        <button className={tab === "logs" ? "active" : ""} onClick={() => setTab("logs")}>Journaux</button>
      </nav>

      {tab === "users" && <UsersTab />}
      {tab === "pages" && <PagesTab />}
      {tab === "logs" && <LogsTab />}
    </>
  );
}

// Formulaire de ré-authentification pour obtenir le jeton d'administration
function AdminUnlock() {
  const { refresh } = useAuth();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api("/auth/admin-session", "POST", { password });
      await refresh(); // hasAdminSession passe à true -> les onglets s'affichent
    } catch (err) {
      setError(errorMessage(err));
      setPassword("");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card narrow">
      <h1>Accès administrateur</h1>
      <p className="alert info">
        Zone sensible : saisissez votre <strong>mot de passe d'administration</strong> (différent de votre
        mot de passe de connexion) pour ouvrir une session d'administration de 15 minutes.
        Cet accès est enregistré dans les journaux.
      </p>
      {error && <p className="alert error">{error}</p>}
      <form onSubmit={submit}>
        <label htmlFor="admin-password">Mot de passe d'administration</label>
        <input id="admin-password" type="password" autoComplete="off" maxLength={128}
          value={password} onChange={(e) => setPassword(e.target.value)} required autoFocus />
        <button className="btn" disabled={loading}>{loading ? "Vérification…" : "Accéder à l'administration"}</button>
      </form>
    </div>
  );
}
