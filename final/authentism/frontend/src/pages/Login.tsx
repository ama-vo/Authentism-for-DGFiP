// Page de connexion en 2 étapes : 1) numéro fiscal + mot de passe  2) code reçu par e-mail
import { FormEvent, useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useAuth } from "../AuthContext";
import { Header } from "../components/Layout";

export default function Login() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const [step, setStep] = useState<"password" | "mfa">("password");
  const [fiscalNumber, setFiscalNumber] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [challengeId, setChallengeId] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function submitPassword(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await api<{ challengeId: string; email: string }>("/auth/login", "POST", { fiscalNumber, password });
      setChallengeId(data.challengeId);
      setEmail(data.email);
      setPassword(""); // on ne garde pas le mot de passe en mémoire plus longtemps que nécessaire
      setStep("mfa");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function submitCode(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api("/auth/mfa", "POST", { challengeId, code });
      await refresh();
      navigate("/");
    } catch (err) {
      setError(errorMessage(err));
      setCode("");
    } finally {
      setLoading(false);
    }
  }

  function restart() {
    setStep("password");
    setCode("");
    setError("");
  }

  return (
    <>
      <Header />
      <main className="container narrow">
        <div className="card">
          <h1>Connexion à votre espace</h1>

          {params.get("expire") && step === "password" && (
            <p className="alert info">Votre session a expiré, veuillez vous reconnecter.</p>
          )}
          {error && <p className="alert error">{error}</p>}

          {step === "password" ? (
            <form onSubmit={submitPassword}>
              <label htmlFor="fiscal">Numéro fiscal</label>
              <input
                id="fiscal"
                inputMode="numeric"
                autoComplete="username"
                maxLength={13}
                placeholder="13 chiffres"
                value={fiscalNumber}
                onChange={(e) => setFiscalNumber(e.target.value.replace(/\D/g, ""))}
                required
              />

              <label htmlFor="password">Mot de passe</label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                maxLength={128}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />

              <button className="btn" disabled={loading || fiscalNumber.length !== 13}>
                {loading ? "Vérification…" : "Continuer"}
              </button>
              <p className="small">
                <Link to="/mot-de-passe-oublie">Mot de passe oublié ?</Link>
              </p>
            </form>
          ) : (
            <form onSubmit={submitCode}>
              <p className="alert info">
                Un code à 6 chiffres a été envoyé à <strong>{email}</strong>. Il est valable 5 minutes.
              </p>
              <label htmlFor="code">Code de vérification</label>
              <input
                id="code"
                className="code-input"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                autoFocus
                required
              />
              <button className="btn" disabled={loading || code.length !== 6}>
                {loading ? "Vérification…" : "Se connecter"}
              </button>
              <p className="small">
                <button type="button" className="btn-link" onClick={restart}>
                  ← Recommencer / renvoyer un code
                </button>
              </p>
            </form>
          )}
        </div>
        <p className="small center">Connexion sécurisée (HTTPS) · authentification à double facteur</p>
      </main>
    </>
  );
}
