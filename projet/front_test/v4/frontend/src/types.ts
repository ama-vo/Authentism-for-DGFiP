export type Role = "external" | "agent" | "admin";
export type Priority = "normal" | "high" | "critical";

export const ROLE_LABELS: Record<Role, string> = {
  external: "Utilisateur externe",
  agent: "Agent DGFiP",
  admin: "Administrateur système",
};

export interface SessionUser {
  fiscal_id: string;
  role: Role;
  name: string;
}

export interface ChallengeResponse {
  challenge_token: string;
  expires_in_seconds: number;
  sent_to?: string;
  message?: string;
  debug_code?: string;
}

export interface DashboardLink {
  slug: string;
  label: string;
  description: string;
  endpoint: string;
  allowed: boolean;
}

export interface StandardPage {
  slug: string;
  label: string;
  description: string;
  content: string;
  role: Role;
}

export interface ManagedPage {
  slug: string;
  label: string;
  description: string;
  content: string;
  roles: Role[];
  visible: boolean;
}

export interface ManagedUser {
  fiscal_id: string;
  name: string;
  email: string;
  role: Role | null;
  locked: boolean;
  active_sessions: number;
}

export interface LogEntry {
  seq: number;
  timestamp: string;
  source: string;
  account: string;
  action: string;
  endpoint: string;
  ip: string;
  priority: Priority;
  outcome: string;
}

export interface PasswordRules {
  length: boolean;
  uppercase: boolean;
  lowercase: boolean;
  digit: boolean;
  special: boolean;
}
