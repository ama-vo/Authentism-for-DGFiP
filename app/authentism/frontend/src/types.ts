// Types partagés par toute l'application

export type Role = "usager" | "agent" | "admin";

export const ROLE_LABELS: Record<Role, string> = {
  usager: "Utilisateur externe",
  agent: "Agent DGFiP",
  admin: "Administrateur",
};

export interface CurrentUser {
  fiscalNumber: string;
  name: string;
  role: Role;
  hasAdminSession: boolean;
}

export interface Page {
  slug: string;
  title: string;
  description: string;
  content: string;
  visible: boolean;
}

export interface AccountUser {
  fiscalNumber: string;
  firstName: string;
  lastName: string;
  email: string;
  role: Role;
}

export interface LogEntry {
  id: number;
  timestamp: string;
  account: string;
  action: string;
  endpoint: string;
  ip: string;
  priority: "INFO" | "ELEVE" | "CRITIQUE";
  success: boolean;
  details: string | null;
}
