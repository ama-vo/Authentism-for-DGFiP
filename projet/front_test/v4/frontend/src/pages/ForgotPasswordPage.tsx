import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError, errorMessage } from "../api/client";
import { PasswordChecklist } from "../components/PasswordChecklist";
import type { ChallengeResponse } from "../types";
import { isFiscalIdValid, isPasswordValid } from "../utils/validation";

export function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [fiscalId, setFiscalId] = useState("");
  const [challenge, setChallenge] = useState<ChallengeResponse | null>(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function requestCode(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!isFiscalIdValid(fiscalId)) {
      setError("Le numéro fiscal doit comporter exactement 13 chiffres.");
      return;
    }
    setLoading(true);
    try {
      const res = await api.forgotPassword(fiscalId);
      setChallenge(res);
      setInfo(res.message ?? null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  function startOver(message: string) {
    setChallenge(null);
    setCode("");
    setError(message);
    setInfo(null);
  }

  async function resend() {
    if (!challenge) return;
    setError(null);
    try {
      const res = await api.resendReset(challenge.challenge_token);
      setChallenge({ ...challenge, ...res });
      setInfo("Si le compte existe, un nouveau code a été envoyé.");
    } catch (err) {
      if (err instanceof ApiError && err.data.restart) startOver(err.message);
      else setError(errorMessage(err));
    }
  }

  async function submitReset(e: FormEvent) {
    e.preventDefault();
    if (!challenge) return;
    setError(null);
    if (!/^\d{6}$/.test(code)) return setError("Le code comporte 6 chiffres.");
    if (!isPasswordValid(password)) return setError("Le mot de passe ne respecte pas la politique de sécurité.");
    if (password !== confirm) return setError("Les deux mots de passe ne correspondent pas.");
    setLoading(true);
    try {
      await api.resetPassword(challenge.challenge_token, code, password);
      navigate("/login", {
        replace: true,
        state: { notice: "Mot de passe modifié. Vous pouvez vous connecter ; vos autres sessions ont été fermées." },
      });
    } catch (err) {
      if (err instanceof ApiError && err.data.restart) startOver(err.message);
      else {
        const remaining = err instanceof ApiError ? err.data.attempts_remaining : undefined;
        setError(remaining !== undefined ? `${errorMessage(err)} Tentatives restantes : ${remaining}.` : errorMessage(err));
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-eyebrow">Réinitialisation du mot de passe</div>
        <h1 className="auth-title">Mot de passe oublié</h1>

        {error && <div className="alert error" role="alert">{error}</div>}
        {info && <div className="alert success">{info}</div>}

        {!challenge ? (
          <form onSubmit={requestCode} noValidate>
            <p className="auth-sub">
              Indiquez votre numéro fiscal : un code de vérification sera envoyé à l'adresse e-mail associée au compte.
            </p>
            <div className="field">
              <label htmlFor="fid">Numéro fiscal (13 chiffres)</label>
              <input
                id="fid"
                type="text"
                inputMode="numeric"
                autoComplete="username"
                maxLength={13}
                value={fiscalId}
                onChange={(e) => setFiscalId(e.target.value.replace(/\D/g, "").slice(0, 13))}
                autoFocus
              />
            </div>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? "Envoi…" : "Recevoir un code"}
            </button>
          </form>
        ) : (
          <form onSubmit={submitReset} noValidate>
            <div className="field">
              <label htmlFor="code">Code reçu par e-mail</label>
              <input
                id="code"
                className="code-input"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                autoFocus
              />
            </div>
            <div className="field">
              <label htmlFor="npw">Nouveau mot de passe</label>
              <input id="npw" type="password" autoComplete="new-password" maxLength={128} value={password}
                onChange={(e) => setPassword(e.target.value)} />
              <PasswordChecklist password={password} />
            </div>
            <div className="field">
              <label htmlFor="cpw">Confirmer le mot de passe</label>
              <input id="cpw" type="password" autoComplete="new-password" maxLength={128} value={confirm}
                onChange={(e) => setConfirm(e.target.value)} />
            </div>
            <button type="submit" className="btn-primary" disabled={loading}>
              {loading ? "Enregistrement…" : "Changer mon mot de passe"}
            </button>
            <button type="button" className="btn-secondary spaced" onClick={resend}>
              Renvoyer un code
            </button>
            {challenge.debug_code && (
              <div className="demo-note">
                Mode démonstration : code <code>{challenge.debug_code}</code>
              </div>
            )}
          </form>
        )}

        <p className="auth-links">
          <Link to="/login">← Retour à la connexion</Link>
        </p>
      </div>
    </div>
  );
}
