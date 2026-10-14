import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import type { StandardPage } from "../types";

export function StandardPageView() {
  const { slug = "" } = useParams();
  const [page, setPage] = useState<StandardPage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPage(null);
    setError(null);
    api.page(slug).then(setPage).catch((err) => setError(errorMessage(err)));
  }, [slug]);

  return (
    <div>
      <div className="portal-head">
        <h1>{page?.label ?? "Page"}</h1>
        <p className="mono">/{slug}.php</p>
      </div>
      {error && <div className="alert error">{error}</div>}
      {page && (
        <div className="panel">
          <p className="muted">{page.description}</p>
          {/* Contenu rendu comme texte (échappé par React) : pas de XSS possible. */}
          <p>{page.content}</p>
        </div>
      )}
      <Link to="/dashboard" className="btn-secondary inline spaced">
        ← Retour au tableau de bord
      </Link>
    </div>
  );
}
