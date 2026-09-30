import type { PasswordRules } from "../types";

export function passwordRules(password: string): PasswordRules {
  return {
    length: password.length >= 12,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    digit: /[0-9]/.test(password),
    special: /[^A-Za-z0-9]/.test(password),
  };
}

export function isPasswordValid(password: string): boolean {
  return Object.values(passwordRules(password)).every(Boolean);
}

export function isFiscalIdValid(fiscalId: string): boolean {
  return /^\d{13}$/.test(fiscalId);
}
