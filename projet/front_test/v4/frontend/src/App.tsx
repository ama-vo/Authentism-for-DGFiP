import { Link, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { useAuth } from "./context/AuthContext";
import { AdminGatePage } from "./pages/AdminGatePage";
import { AdminPage } from "./pages/AdminPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { LoginPage } from "./pages/LoginPage";
import { MfaPage } from "./pages/MfaPage";
import { StandardPageView } from "./pages/StandardPageView";
import { ROLE_LABELS } from "./types";

function Masthead() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <header className="masthead">
      <Link to={user ? "/dashboard" : "/login"} className="brand">
        <svg className="brand-mark" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <rect x="1" y="1" width="38" height="38" rx="3" stroke="currentColor" strokeWidth="1.6" />
          <path d="M20 8 L30 13 V21 C30 27.5 25.8 31.7 20 33.5 C14.2 31.7 10 27.5 10 21 V13 Z" stroke="currentColor" strokeWidth="1.6" />
          <circle cx="20" cy="19" r="3" stroke="currentColor" strokeWidth="1.6" />
          <path d="M20 22 V27" stroke="currentColor" strokeWidth="1.6" />
        </svg>
        <div className="brand-text">
          <div className="service">Portail sécurisé</div>
          <div className="org">Direction générale des Finances publiques</div>
        </div>
      </Link>
      {user && (
        <div className="session-chip">
          <span>
            <strong>{user.name}</strong>
            <span className="muted"> · {ROLE_LABELS[user.role]}</span>
          </span>
          <button type="button" className="btn-logout" onClick={handleLogout}>
            Se déconnecter
          </button>
        </div>
      )}
    </header>
  );
}

export default function App() {
  const { user } = useAuth();
  return (
    <div>
      <Masthead />
      <main>
        <Routes>
          <Route path="/login" element={user ? <Navigate to="/dashboard" replace /> : <LoginPage />} />
          <Route path="/mfa" element={<MfaPage />} />
          <Route path="/mot-de-passe-oublie" element={<ForgotPasswordPage />} />
          <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/p/:slug" element={<ProtectedRoute><StandardPageView /></ProtectedRoute>} />
          <Route path="/admin/acces" element={<ProtectedRoute><AdminGatePage /></ProtectedRoute>} />
          <Route path="/admin" element={<ProtectedRoute><AdminPage /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to={user ? "/dashboard" : "/login"} replace />} />
        </Routes>
      </main>
      <footer className="site-footer">Authentism pour la DGFiP — projet pédagogique</footer>
    </div>
  );
}
