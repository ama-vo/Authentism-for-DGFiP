import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { Role } from "../types";

interface AuthState {
  token: string | null; // jeton de session "normal", émis après le 2FA
  adminToken: string | null; // jeton scopé /admin.php, obtenu par échange (flux 10/11)
  role: Role | null;
  fiscalId: string | null;
}

interface AuthContextValue extends AuthState {
  setSession: (data: { token: string; role: Role; fiscalId: string }) => void;
  setAdminToken: (token: string) => void;
  clear: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);
const initialState: AuthState = { token: null, adminToken: null, role: null, fiscalId: null };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(initialState);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      setSession: ({ token, role, fiscalId }) => setState((s) => ({ ...s, token, role, fiscalId })),
      setAdminToken: (adminToken) => setState((s) => ({ ...s, adminToken })),
      clear: () => setState(initialState),
    }),
    [state]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé à l'intérieur d'un <AuthProvider>.");
  return ctx;
}

// Les jetons ne sont conservés qu'en mémoire (jamais dans
// localStorage/sessionStorage) pour limiter l'exposition en cas de
// XSS — cohérent avec le fait que c'est le Système d'authentification,
// pas le navigateur, qui fait foi de la session.
