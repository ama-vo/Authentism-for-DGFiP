// Liste des routes (pages) de l'application
import { Routes, Route, Navigate } from "react-router-dom";
import { ReactNode } from "react";
import { useAuth } from "./AuthContext";
import { Role } from "./types";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import Dashboard from "./pages/Dashboard";
import StandardPage from "./pages/StandardPage";
import Admin from "./pages/Admin";

// Protège une page : redirige vers la connexion si besoin.
// Attention : ce n'est que du confort d'affichage, la vraie sécurité
// est vérifiée côté serveur (whitelist.ts) à chaque appel d'API.
function Protected({ children, role }: { children: ReactNode; role?: Role }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="center">Chargement…</p>;
  if (!user) return <Navigate to="/connexion" replace />;
  if (role && user.role !== role) return <Navigate to="/" replace />;
  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/connexion" element={<Login />} />
      <Route path="/mot-de-passe-oublie" element={<ForgotPassword />} />
      <Route path="/reinitialiser" element={<ResetPassword />} />

      <Route path="/" element={<Protected><Dashboard /></Protected>} />
      <Route path="/page/:slug" element={<Protected><StandardPage /></Protected>} />
      <Route path="/admin" element={<Protected role="admin"><Admin /></Protected>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
