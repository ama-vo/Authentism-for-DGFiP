import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { DashboardLink } from "../types";

const ROLE_LABELS: Record<string, string> = {
  external: "Utilisateur externe",
  agent: "Agent DGFiP",
  admin: "Administrateur système",
};

export function DashboardPage() {
  const { token, role, fiscalId, clear } = useAuth();
  const navigate = useNavigate();
  const [links, setLinks] = useState<DashboardLink[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    api
      .dashboard(token)
      .then((res) => setLinks(res.links))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur de chargement."));
  }, [token]);

  async function handleLogout() {
    if (token) {
      try {
        await api.logout(token);
      } catch {
        // la session côté serveur peut déjà avoir expiré
      }
    }
    clear();
    navigate("/login", { replace: true });
  }

  return (
    <div>
      <div className="session-bar">
        <span>
          Connecté en tant que <strong>{fiscalId}</strong> — {ROLE_LABELS[role ?? ""]}
        </span>
        <button className="btn-logout" onClick={handleLogout}>
          Se déconnecter
        </button>
      </div>

      <div className="portal-head">
        <h1>Tableau de bord</h1>
        <p>
          Chaque lien ci-dessous a été vérifié individuellement par le modèle RBAC (LDAP) — flux 7/8 du
          schéma.
        </p>
      </div>

      {error && <div className="alert error">{error}</div>}

      <div className="tile-grid">
        {links.map((link) => {
          const to =
            link.endpoint === "/admin.php"
              ? "/admin/gate"
              : link.endpoint === "/page1.php"
              ? "/page1"
              : "/dashboard";
          return link.allowed ? (
            <Link key={link.endpoint} to={to} className="tile">
              <div className="tile-top" />
              <h3>{link.label}</h3>
              <p className="tile-endpoint">{link.endpoint}</p>
            </Link>
          ) : (
            <div key={link.endpoint} className="tile locked">
              <div className="tile-top">
                <span className="lock-pill">Accès restreint</span>
              </div>
              <h3>{link.label}</h3>
              <p className="tile-endpoint">{link.endpoint}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
