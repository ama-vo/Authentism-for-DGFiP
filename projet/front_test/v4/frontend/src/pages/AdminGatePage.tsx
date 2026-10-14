import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api/client";

// Flux 10/11 : le serveur vérifie l'appartenance au groupe LDAP « admins »,
// redemande le mot de passe, puis échange la session contre un jeton
// administrateur distinct, de courte durée, limité à /admin.php.
export function AdminGatePage() {
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.adminToken(password);
      setPassword("");
      navigate("/admin", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-eyebrow">Accès sensible</div>
        <h1 className="auth-title">Panneau d'administration</h1>
        <p className="auth-sub">
          Confirmez votre mot de passe pour obtenir un jeton d'administration (valable 10 minutes, limité à{" "}
          <code>/admin.php</code>). Cet accès est journalisé avec une priorité élevée.
        </p>
        {error && <div className="alert error" role="alert">{error}</div>}
        <form onSubmit={handleSubmit} noValidate>
          <div className="field">
            <label htmlFor="apw">Mot de passe</label>
            <input id="apw" type="password" autoComplete="current-password" maxLength={128} value={password}
              onChange={(e) => setPassword(e.target.value)} autoFocus />
          </div>
          <button type="submit" className="btn-primary" disabled={loading || !password}>
            {loading ? "Vérification…" : "Obtenir le jeton d'administration"}
          </button>
          <button type="button" className="btn-secondary spaced" onClick={() => navigate("/dashboard")}>
            Retour au tableau de bord
          </button>
        </form>
      </div>
    </div>
  );
}
