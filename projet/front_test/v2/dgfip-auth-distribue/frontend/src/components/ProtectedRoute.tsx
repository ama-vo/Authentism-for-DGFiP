import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function ProtectedRoute({
  children,
  requireAdminToken = false,
}: {
  children: ReactNode;
  requireAdminToken?: boolean;
}) {
  const { token, adminToken } = useAuth();

  if (!token) return <Navigate to="/login" replace />;
  if (requireAdminToken && !adminToken) return <Navigate to="/admin/gate" replace />;

  return <>{children}</>;
}
