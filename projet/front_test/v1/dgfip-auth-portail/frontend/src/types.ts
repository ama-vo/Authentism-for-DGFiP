export type Role = "external" | "agent" | "admin";

export interface Service {
  id: string;
  name: string;
  allowed: boolean;
}

export interface Account {
  id: number;
  fiscal_id: string;
  name: string;
  role: Role;
  created_at: string;
}

export interface LogEntry {
  id: number;
  timestamp: string;
  account: string;
  action: string;
  endpoint: string;
  ip_address: string;
  priority: "normal" | "high";
}

export interface PasswordRules {
  length: boolean;
  uppercase: boolean;
  lowercase: boolean;
  digit: boolean;
  special: boolean;
}
