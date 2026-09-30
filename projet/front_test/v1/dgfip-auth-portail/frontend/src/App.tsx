import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AdminGatePage } from "./pages/AdminGatePage";
import { AdminPage } from "./pages/AdminPage";
import { LoginPage } from "./pages/LoginPage";
import { MfaPage } from "./pages/MfaPage";
import { PortalPage } from "./pages/PortalPage";

export default function App() {
  return (
    <div>
      <header className="masthead">
        <div className="brand">
          <svg className="brand-mark" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="1" y="1" width="38" height="38" rx="3" stroke="var(--primary)" strokeWidth="1.6" />
            <path
              d="M20 8 L30 13 V21 C30 27.5 25.8 31.7 20 33.5 C14.2 31.7 10 27.5 10 21 V13 Z"
              stroke="var(--primary)"
              strokeWidth="1.6"
              fill="none"
            />
            <circle cx="20" cy="19" r="3" stroke="var(--primary)" strokeWidth="1.6" fill="none" />
            <path d="M20 22 V27" stroke="var(--primary)" strokeWidth="1.6" />
          </svg>
          <div className="brand-text">
            <div className="service">Portail Sécurisé</div>
            <div className="org">Direction générale des Finances publiques</div>
          </div>
        </div>
      </header>

      <main>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/mfa" element={<MfaPage />} />
          <Route
            path="/portail"
            element={
              <ProtectedRoute>
                <PortalPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/gate"
            element={
              <ProtectedRoute allowRoles={["admin"]}>
                <AdminGatePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute requireAdminToken allowRoles={["admin"]}>
                <AdminPage />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </main>
    </div>
  );
}
