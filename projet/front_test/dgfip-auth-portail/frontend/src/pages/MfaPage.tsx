import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";

interface LocationState {
  pendingToken: string;
  debugCode?: string;
}

export function MfaPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setSession } = useAuth();

  const initialState = location.state as LocationState | undefined;
  const pendingToken = initialState?.pendingToken ?? "";
  const [debugCode, setDebugCode] = useState(initialState?.debugCode);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!initialState?.pendingToken) {
    navigate("/login", { replace: true });
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.verifyMfa(pendingToken, code);
      setSession({ token: res.token, role: res.role as never, fiscalId: res.fiscal_id, name: res.name });
      navigate("/portail", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de contacter le serveur.");
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    setError(null);
    try {
      const res = await api.resendMfa(pendingToken);
      setDebugCode(res.debug_code);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de renvoyer le code.");
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-eyebrow">Double authentification</div>
        <h1 className="auth-title">Vérification en deux étapes</h1>
        <p className="auth-sub">
          Un code à 6 chiffres a été envoyé à l'adresse e-mail associée à votre compte.
        </p>

        {error && <div className="alert error">{error}</div>}

        <form onSubmit={handleSubmit} noValidate>
          <div className="field">
            <label htmlFor="mfaCode">Code de vérification</label>
            <input
              id="mfaCode"
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="000000"
              style={{ letterSpacing: "0.3em", textAlign: "center", fontSize: 19 }}
            />
          </div>
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "Vérification…" : "Valider le code"}
          </button>
          <button type="button" className="btn-secondary" style={{ marginTop: 10 }} onClick={handleResend}>
            Renvoyer le code
          </button>
        </form>

        {debugCode && (
          <div className="demo-note">
            Environnement de démonstration sans serveur de messagerie : code généré —{" "}
            <code>{debugCode}</code>
          </div>
        )}
      </div>
    </div>
  );
}
