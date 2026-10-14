// Tableau de bord : menu des pages disponibles (SSO : une seule connexion pour tous les services)
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useAuth } from "../AuthContext";
import { Page } from "../types";

export default function Dashboard() {
  const { user } = useAuth();
  const [pages, setPages] = useState<Page[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ pages: Page[] }>("/pages")
      .then((data) => setPages(data.pages))
      .catch((err) => setError(errorMessage(err)));
  }, []);

  return (
    <>
      <h1>Bonjour {user?.name}</h1>
      <p className="muted">Numéro fiscal : {user?.fiscalNumber}</p>
      {error && <p className="alert error">{error}</p>}

      <h2>Mes services</h2>
      <div className="grid">
        {pages.map((page) => (
          <Link key={page.slug} to={`/page/${page.slug}`} className="tile">
            <strong>{page.title}</strong>
            <span>{page.description}</span>
          </Link>
        ))}

        {/* Lien affiché seulement pour l'admin (le serveur vérifie de toute façon) */}
        {user?.role === "admin" && (
          <Link to="/admin" className="tile tile-admin">
            <strong>Administration</strong>
            <span>Comptes, pages du dashboard et journaux.</span>
          </Link>
        )}
      </div>
    </>
  );
}
