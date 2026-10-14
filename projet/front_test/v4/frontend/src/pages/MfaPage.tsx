import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { api, ApiError, errorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type { ChallengeResponse } from "../types";

export function MfaPage() {
  const location = useLocation();
  const challenge = (location.state as { challenge?: ChallengeResponse } | null)?.challenge;
  // Correction v3 : on ne navigue plus pendant le rendu (avertissement
  // React) — on rend un <Navigate> déclaratif.
  if (!challenge?.challenge_token) return <Navigate to="/login" replace />;
  return <MfaForm initial={challenge} />;
}

function MfaForm({ initial }: { initial: ChallengeResponse }) {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [challenge, setChallenge] = useState(initial);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function restart(message: string) {
    navigate("/login", { replace: true, state: { notice: message } });
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    if (!/^\d{6}$/.test(code)) {
      setError("Le code comporte 6 chiffres.");
      return;
    }
    setLoading(true);
    try {
      const res = await api.verifyMfa(challenge.challenge_token, code);
      setUser({ fiscal_id: res.fiscal_id, role: res.role, name: res.name });
      navigate("/dashboard", { replace: true }); // flux 6 : redirection vers /dashboard.php
    } catch (err) {
      if (err instanceof ApiError && err.data.restart) {
        restart(err.message);
        return;
      }
      const remaining = err instanceof ApiError ? err.data.attempts_remaining : undefined;
      setError(remaining !== undefined ? `${errorMessage(err)} Tentatives restantes : ${remaining}.` : errorMessage(err));
      setCode("");
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    setError(null);
    try {
      const res = await api.resendMfa(challenge.challenge_token);
      setChallenge({ ...challenge, ...res });
      setInfo("Un nouveau code vient d'être envoyé.");
    } catch (err) {
      if (err instanceof ApiError && err.data.restart) restart(err.message);
      else setError(errorMessage(err));
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-eyebrow">Étape 2 sur 2 — Double authentification</div>
        <h1 className="auth-title">Vérification en deux étapes</h1>
        <p className="auth-sub">
          Un code à 6 chiffres a été envoyé à <strong>{challenge.sent_to ?? "votre adresse e-mail"}</strong>. Il expire
          dans {Math.round(challenge.expires_in_seconds / 60)} minutes.
        </p>

        {error && <div className="alert error" role="alert">{error}</div>}
        {info && <div className="alert success">{info}</div>}

        <form onSubmit={handleSubmit} noValidate>
          <div className="field">
            <label htmlFor="mfaCode">Code de vérification</label>
            <input
              id="mfaCode"
              className="code-input"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="000000"
              autoFocus
            />
          </div>
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "Vérification…" : "Valider le code"}
          </button>
          <button type="button" className="btn-secondary spaced" onClick={handleResend}>
            Renvoyer un code
          </button>
        </form>

        {challenge.debug_code && (
          <div className="demo-note">
            Mode démonstration (DEBUG_EXPOSE_MFA_CODE) : code <code>{challenge.debug_code}</code>
          </div>
        )}
      </div>
    </div>
  );
}
