// Mot de passe oublié : on demande le numéro fiscal, un lien est envoyé par e-mail
import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";
import { Header } from "../components/Layout";

export default function ForgotPassword() {
  const [fiscalNumber, setFiscalNumber] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await api<{ message: string }>("/auth/forgot-password", "POST", { fiscalNumber });
      setMessage(data.message);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Header />
      <main className="container narrow">
        <div className="card">
          <h1>Mot de passe oublié</h1>
          {error && <p className="alert error">{error}</p>}

          {message ? (
            <p className="alert success">{message}</p>
          ) : (
            <form onSubmit={submit}>
              <p>Saisissez votre numéro fiscal. Vous recevrez un lien pour choisir un nouveau mot de passe.</p>
              <label htmlFor="fiscal">Numéro fiscal</label>
              <input
                id="fiscal"
                inputMode="numeric"
                maxLength={13}
                placeholder="13 chiffres"
                value={fiscalNumber}
                onChange={(e) => setFiscalNumber(e.target.value.replace(/\D/g, ""))}
                required
              />
              <button className="btn" disabled={loading || fiscalNumber.length !== 13}>
                {loading ? "Envoi…" : "Recevoir le lien"}
              </button>
            </form>
          )}
          <p className="small">
            <Link to="/connexion">← Retour à la connexion</Link>
          </p>
        </div>
      </main>
    </>
  );
}
