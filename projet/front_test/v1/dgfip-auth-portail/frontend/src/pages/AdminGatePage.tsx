import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";

export function AdminGatePage() {
  const { token, setAdminToken } = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setError(null);
    setLoading(true);
    try {
      const res = await api.getAdminToken(token, password);
      setAdminToken(res.admin_token);
      navigate("/admin", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de contacter le serveur.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="admin-gate">
      <div className="auth-card">
        <div className="auth-eyebrow">Panneau d'administration</div>
        <h1 className="auth-title" style={{ fontSize: 21 }}>
          Confirmation requise
        </h1>
        <p className="auth-sub">
          L'accès au portail d'administration nécessite un jeton de session dédié, distinct de votre
          session courante. Confirmez votre mot de passe pour l'obtenir.
        </p>
        {error && <div className="alert error">{error}</div>}
        <form onSubmit={handleSubmit} noValidate>
          <div className="field">
            <label htmlFor="adminPw">Mot de passe</label>
            <input
              id="adminPw"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
            />
          </div>
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "Vérification…" : "Obtenir le jeton d'administration"}
          </button>
        </form>
        <button type="button" className="btn-secondary" style={{ marginTop: 10 }} onClick={() => navigate("/portail")}>
          Retour au portail
        </button>
      </div>
    </div>
  );
}
