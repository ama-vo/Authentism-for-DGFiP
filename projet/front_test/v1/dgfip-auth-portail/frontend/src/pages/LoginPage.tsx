import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { PasswordChecklist } from "../components/PasswordChecklist";
import { isFiscalIdValid, isPasswordValid } from "../utils/validation";

export function LoginPage() {
  const navigate = useNavigate();
  const [fiscalId, setFiscalId] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!isFiscalIdValid(fiscalId)) {
      setError("Le numéro fiscal doit comporter exactement 13 chiffres.");
      return;
    }
    if (!isPasswordValid(password)) {
      setError("Le mot de passe ne respecte pas la politique de sécurité requise.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.login(fiscalId, password);
      navigate("/mfa", {
        state: { pendingToken: res.pending_token, debugCode: res.debug_code },
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de contacter le serveur.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-eyebrow">Identification</div>
        <h1 className="auth-title">Accéder à votre espace</h1>
        <p className="auth-sub">
          Saisissez votre numéro fiscal et votre mot de passe pour accéder aux services de la DGFiP.
        </p>

        {error && <div className="alert error">{error}</div>}

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
            />
          </div>

          <div className="field">
            <label htmlFor="pw">Mot de passe</label>
            <div className="pw-row">
              <input
                id="pw"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
              />
              <button type="button" className="pw-toggle" onClick={() => setShowPassword((s) => !s)}>
                {showPassword ? "masquer" : "afficher"}
              </button>
            </div>
            <PasswordChecklist password={password} />
          </div>

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "Connexion…" : "Se connecter"}
          </button>
        </form>

        <div className="demo-note">
          Comptes de démonstration (voir <code>backend/seed.py</code>) : agent, utilisateur externe et
          administrateur système.
        </div>
      </div>
    </div>
  );
}
