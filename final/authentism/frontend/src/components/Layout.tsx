// En-tête + contenu, pour toutes les pages où l'on est connecté
import { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { ROLE_LABELS } from "../types";

export function Header({ children }: { children?: ReactNode }) {
  return (
    <header className="header">
      <div className="flag" />
      <div className="header-inner">
        <Link to="/" className="brand">
          <span className="brand-title">Finances publiques</span>
          <span className="brand-sub">Espace sécurisé · Authentism</span>
        </Link>
        {children}
      </div>
    </header>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/connexion");
  }

  return (
    <>
      <Header>
        {user && (
          <div className="user-box">
            <div>
              <strong>{user.name}</strong>
              <span className="badge">{ROLE_LABELS[user.role]}</span>
            </div>
            <button className="btn-link" onClick={handleLogout}>Se déconnecter</button>
          </div>
        )}
      </Header>
      <main className="container">{children}</main>
    </>
  );
}
