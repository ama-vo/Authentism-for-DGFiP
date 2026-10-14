import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError, errorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { DashboardLink } from "../types";

export function DashboardPage() {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [links, setLinks] = useState<DashboardLink[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .dashboard()
      .then((res) => setLinks(res.links))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          setUser(null);
          navigate("/login", { replace: true, state: { notice: "Votre session a expiré." } });
        } else setError(errorMessage(err));
      });
  }, [navigate, setUser]);

  return (
    <div>
      <div className="portal-head">
        <h1>Tableau de bord</h1>
        <p>Les pages disponibles dépendent de votre rôle. Chaque accès est vérifié par le serveur.</p>
      </div>

      {error && <div className="alert error">{error}</div>}
      {!links && !error && <div className="loading">Chargement…</div>}

      <div className="tile-grid">
        {links?.map((link) => {
          const to = link.slug === "admin" ? "/admin/acces" : `/p/${link.slug}`;
          const content = (
            <>
              <div className="tile-top">{!link.allowed && <span className="lock-pill">Accès restreint</span>}</div>
              <h3>{link.label}</h3>
              <p className="tile-desc">{link.description}</p>
              <p className="tile-endpoint">{link.endpoint}</p>
            </>
          );
          return link.allowed ? (
            <Link key={link.slug} to={to} className={`tile${link.slug === "admin" ? " tile-admin" : ""}`}>
              {content}
            </Link>
          ) : (
            <div key={link.slug} className="tile locked" aria-disabled="true">
              {content}
            </div>
          );
        })}
      </div>
    </div>
  );
}
