import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";

export function AdminGatePage() {
  const { token, setAdminToken } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleExchange() {
    if (!token) return;
    setError(null);
    setLoading(true);
    try {
      const res = await api.getAdminToken(token);
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
        <div className="auth-eyebrow">POST /admin.php/token</div>
        <h1 className="auth-title" style={{ fontSize: 21 }}>
          Échange de jeton administrateur
        </h1>
        <p className="auth-sub">
          Le Système d'authentification va vérifier votre appartenance au groupe LDAP <code>admins</code>{" "}
          puis délivrer un second jeton, distinct de votre session normale et strictement limité à{" "}
          <code>/admin.php</code> (flux 10/11 du schéma).
        </p>
        {error && <div className="alert error">{error}</div>}
        <button type="button" className="btn-primary" onClick={handleExchange} disabled={loading}>
          {loading ? "Vérification…" : "Obtenir le jeton d'administration"}
        </button>
        <button type="button" className="btn-secondary" style={{ marginTop: 10 }} onClick={() => navigate("/dashboard")}>
          Retour au tableau de bord
        </button>
      </div>
    </div>
  );
}
