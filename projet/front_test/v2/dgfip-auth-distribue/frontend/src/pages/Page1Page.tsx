import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";

export function Page1Page() {
  const { token } = useAuth();
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    api
      .page1(token)
      .then((res) => setContent(res.content))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur de chargement."));
  }, [token]);

  return (
    <div>
      <div className="portal-head">
        <h1>Page 1</h1>
        <p>Exemple de « tout autre endpoint », accessible aux agents et administrateurs uniquement.</p>
      </div>
      {error && <div className="alert error">{error}</div>}
      {content && <div className="panel">{content}</div>}
      <Link to="/dashboard" className="btn-secondary" style={{ display: "inline-block", width: "auto", marginTop: 20 }}>
        ← Retour au tableau de bord
      </Link>
    </div>
  );
}
