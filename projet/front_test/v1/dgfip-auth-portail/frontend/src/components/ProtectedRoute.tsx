import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import type { Role } from "../types";

export function ProtectedRoute({
  children,
  requireAdminToken = false,
  allowRoles,
}: {
  children: ReactNode;
  requireAdminToken?: boolean;
  allowRoles?: Role[];
}) {
  const { token, adminToken, role } = useAuth();

  if (!token) return <Navigate to="/login" replace />;
  if (requireAdminToken && !adminToken) return <Navigate to="/admin/gate" replace />;
  if (allowRoles && role && !allowRoles.includes(role)) return <Navigate to="/portail" replace />;

  return <>{children}</>;
}
