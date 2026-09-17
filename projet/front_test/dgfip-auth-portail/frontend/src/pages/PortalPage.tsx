import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { Service } from "../types";

const ROLE_LABELS: Record<string, string> = {
  external: "Utilisateur externe",
  agent: "Agent DGFiP",
  admin: "Administrateur système",
};

export function PortalPage() {
  const { token, role, fiscalId, name, clear } = useAuth();
  const navigate = useNavigate();
  const [services, setServices] = useState<Service[]>([]);
  const [toast, setToast] = useState<{ text: string; kind: "success" | "error" } | null>(null);

  useEffect(() => {
    if (!token) return;
    api.listServices(token).then(setServices).catch(() => setServices([]));
  }, [token]);

  function showToast(text: string, kind: "success" | "error") {
    setToast({ text, kind });
    setTimeout(() => setToast(null), 3200);
  }

  async function handleTileClick(service: Service) {
    if (service.id === "admin") {
      navigate("/admin/gate");
      return;
    }
    if (!service.allowed) {
      showToast("Accès refusé — cette action a été journalisée.", "error");
      return;
    }
    if (!token) return;
    try {
      await api.accessService(token, service.id);
      showToast(`Accès autorisé à « ${service.name} ».`, "success");
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : "Accès refusé.", "error");
    }
  }

  async function handleLogout() {
    if (token) {
      try {
        await api.logout(token);
      } catch {
        // La session côté serveur peut déjà avoir expiré : on
        // nettoie l'état local dans tous les cas.
      }
    }
    clear();
    navigate("/login", { replace: true });
  }

  const tiles: Array<Service & { locked?: boolean }> = [
    ...services,
    { id: "admin", name: "Panneau d'administration", allowed: role === "admin" },
  ];

  return (
    <div>
      <div className="session-bar">
        <span>
          Connecté en tant que <strong>{name ?? fiscalId}</strong> — {ROLE_LABELS[role ?? ""]}
        </span>
        <button className="btn-logout" onClick={handleLogout}>
          Se déconnecter
        </button>
      </div>

      <div className="portal-head">
        <h1>Bienvenue sur votre espace</h1>
        <p>Sélectionnez un service ci-dessous. L'accès à chaque service est vérifié individuellement.</p>
        <div className="sso-badge">
          <span className="dot" /> Authentification unique active — session SSO ouverte
        </div>
      </div>

      <div className="tile-grid">
        {tiles.map((service) => (
          <button
            key={service.id}
            type="button"
            className={"tile" + (service.allowed ? "" : " locked")}
            onClick={() => handleTileClick(service)}
          >
            <div className="tile-top">
              {!service.allowed && <span className="lock-pill">Accès restreint</span>}
            </div>
            <h3>{service.name}</h3>
          </button>
        ))}
      </div>

      {toast && <div className={`toast show ${toast.kind}`}>{toast.text}</div>}
    </div>
  );
}
