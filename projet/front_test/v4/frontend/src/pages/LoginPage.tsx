import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import { isFiscalIdValid } from "../utils/validation";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const notice = (location.state as { notice?: string } | null)?.notice;
  const [fiscalId, setFiscalId] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!isFiscalIdValid(fiscalId)) {
      setError("Le numéro fiscal doit comporter exactement 13 chiffres.");
      return;
    }
    if (!password) {
      setError("Saisissez votre mot de passe.");
      return;
    }
    setLoading(true);
    try {
      const res = await api.login(fiscalId, password);
      setPassword("");
      navigate("/mfa", { state: { challenge: res } });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-eyebrow">Étape 1 sur 2 — Identification</div>
        <h1 className="auth-title">Accéder à votre espace</h1>
        <p className="auth-sub">Saisissez votre numéro fiscal et votre mot de passe.</p>

        {notice && <div className="alert success">{notice}</div>}
        {error && <div className="alert error" role="alert">{error}</div>}

        <form onSubmit={handleSubmit} noValidate>
          <div className="field">
            <label htmlFor="fiscalId">Numéro fiscal (13 chiffres)</label>
            <input
              id="fiscalId"
              type="text"
              inputMode="numeric"
              autoComplete="username"
              maxLength={13}
              value={fiscalId}
              onChange={(e) => setFiscalId(e.target.value.replace(/\D/g, "").slice(0, 13))}
              placeholder="1234567890123"
              autoFocus
            />
          </div>

          <div className="field">
            <label htmlFor="pw">Mot de passe</label>
            <div className="pw-row">
              <input
                id="pw"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                maxLength={128}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
              />
              <button type="button" className="pw-toggle" onClick={() => setShowPassword((s) => !s)}>
                {showPassword ? "masquer" : "afficher"}
              </button>
            </div>
          </div>

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "Vérification…" : "Continuer"}
          </button>
        </form>

        <p className="auth-links">
          <Link to="/mot-de-passe-oublie">Mot de passe oublié ?</Link>
        </p>

        <details className="demo-note">
          <summary>Comptes de démonstration</summary>
          <table className="demo-table">
            <tbody>
              <tr><td>Agent DGFiP</td><td className="mono">1032005849213</td><td className="mono">Agent!DGFiP2026</td></tr>
              <tr><td>Usager externe</td><td className="mono">2098741562034</td><td className="mono">Usager!Externe26</td></tr>
              <tr><td>Administrateur</td><td className="mono">3011008876521</td><td className="mono">Admin!SysDGFiP26</td></tr>
            </tbody>
          </table>
          Le code de vérification arrive dans la boîte mail de démonstration (Mailpit,{" "}
          <span className="mono">http://localhost:8025</span>).
        </details>
      </div>
    </div>
  );
}
