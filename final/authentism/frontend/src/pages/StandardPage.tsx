// Page standard (déclaration, documents...) : le contenu vient de la base de données.
// React échappe automatiquement le texte affiché : pas de risque de XSS
// (on n'utilise JAMAIS dangerouslySetInnerHTML dans ce projet).
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { Page } from "../types";

export default function StandardPage() {
  const { slug } = useParams();
  const [page, setPage] = useState<Page | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ page: Page }>(`/pages/${encodeURIComponent(slug || "")}`)
      .then((data) => setPage(data.page))
      .catch((err) => setError(errorMessage(err)));
  }, [slug]);

  return (
    <>
      <p><Link to="/">← Retour au tableau de bord</Link></p>
      {error && <p className="alert error">{error}</p>}
      {page && (
        <div className="card">
          <h1>{page.title}</h1>
          <p className="muted">{page.description}</p>
          <p>{page.content}</p>
        </div>
      )}
    </>
  );
}
