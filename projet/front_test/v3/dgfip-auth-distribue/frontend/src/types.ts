export type Role = "external" | "agent" | "admin";

export interface DashboardLink {
  endpoint: string;
  label: string;
  allowed: boolean;
}

export interface LogEntry {
  timestamp: string;
  source: string;
  account: string;
  action: string;
  endpoint: string;
  ip: string;
  priority: "normal" | "high";
}

export interface PasswordRules {
  length: boolean;
  uppercase: boolean;
  lowercase: boolean;
  digit: boolean;
  special: boolean;
}
