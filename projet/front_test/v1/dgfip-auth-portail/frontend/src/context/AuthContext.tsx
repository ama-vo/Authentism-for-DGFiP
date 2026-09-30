import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import type { Role } from "../types";

interface AuthState {
  token: string | null; // jeton de session "normal"
  adminToken: string | null; // jeton de session "admin", distinct et à durée de vie plus courte
  role: Role | null;
  fiscalId: string | null;
  name: string | null;
}

interface AuthContextValue extends AuthState {
  setSession: (data: { token: string; role: Role; fiscalId: string; name: string }) => void;
  setAdminToken: (token: string) => void;
  clear: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const initialState: AuthState = {
  token: null,
  adminToken: null,
  role: null,
  fiscalId: null,
  name: null,
};

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(initialState);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      setSession: ({ token, role, fiscalId, name }) =>
        setState((s) => ({ ...s, token, role, fiscalId, name })),
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

// Remarque de sécurité : les jetons ne sont conservés qu'en mémoire
// (état React), jamais dans localStorage/sessionStorage, pour limiter
// l'exposition en cas de XSS. Une session se termine donc au
// rechargement de la page — c'est le compromis retenu pour ce
// prototype. En production, préférer un cookie httpOnly + Secure émis
// par le serveur, combiné à un jeton CSRF pour les requêtes mutatives.
