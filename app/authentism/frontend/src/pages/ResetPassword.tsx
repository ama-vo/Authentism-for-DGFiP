// Choix du nouveau mot de passe, depuis le lien reçu par e-mail (?token=...)
import { FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { Header } from "../components/Layout";
import PasswordRules, { isStrongPassword } from "../components/PasswordRules";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) return setError("Les deux mots de passe ne correspondent pas");
    setError("");
    setLoading(true);
    try {
      await api("/auth/reset-password", "POST", { token, newPassword: password });
      setDone(true);
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
          <h1>Nouveau mot de passe</h1>
          {error && <p className="alert error">{error}</p>}

          {done ? (
            <>
              <p className="alert success">Votre mot de passe a été modifié. Toutes vos sessions ont été fermées.</p>
              <Link className="btn" to="/connexion">Se connecter</Link>
            </>
          ) : !token ? (
            <p className="alert error">Lien invalide. Refaites une demande de réinitialisation.</p>
          ) : (
            <form onSubmit={submit}>
              <label htmlFor="password">Nouveau mot de passe</label>
              <input id="password" type="password" autoComplete="new-password" maxLength={128}
                value={password} onChange={(e) => setPassword(e.target.value)} required />
              <PasswordRules password={password} />

              <label htmlFor="confirm">Confirmer le mot de passe</label>
              <input id="confirm" type="password" autoComplete="new-password" maxLength={128}
                value={confirm} onChange={(e) => setConfirm(e.target.value)} required />

              <button className="btn" disabled={loading || !isStrongPassword(password)}>
                {loading ? "Enregistrement…" : "Valider"}
              </button>
            </form>
          )}
        </div>
      </main>
    </>
  );
}
