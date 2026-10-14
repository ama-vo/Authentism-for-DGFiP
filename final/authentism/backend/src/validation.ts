// Validation stricte de toutes les données reçues (protection contre les injections).
// Principe : on n'accepte QUE ce qui correspond exactement au format attendu
// (liste blanche), tout le reste est refusé avant d'arriver dans le code métier.
import { z } from "zod";
import { ROLES } from "./ldap";

// Numéro fiscal : exactement 13 chiffres, rien d'autre
export const fiscalNumber = z.string().regex(/^\d{13}$/, "Le numéro fiscal doit contenir 13 chiffres");

// Règles du cahier des charges : 12 caractères min, majuscule, minuscule, chiffre, caractère spécial
export const strongPassword = z
  .string()
  .min(12, "12 caractères minimum")
  .max(128, "128 caractères maximum")
  .regex(/[A-Z]/, "Au moins une majuscule")
  .regex(/[a-z]/, "Au moins une minuscule")
  .regex(/[0-9]/, "Au moins un chiffre")
  .regex(/[^A-Za-z0-9]/, "Au moins un caractère spécial");

// Pour la connexion on ne vérifie que la longueur (les règles sont vérifiées à la création)
const anyPassword = z.string().min(1).max(128);

// Noms : lettres (accents compris), espaces, tirets et apostrophes uniquement
const name = z.string().trim().min(1).max(50).regex(/^[A-Za-zÀ-ÿ' -]+$/, "Caractères non autorisés");

// Jetons aléatoires générés par le serveur (64 caractères hexadécimaux)
const token = z.string().regex(/^[a-f0-9]{64}$/, "Jeton invalide");

export const schemas = {
  login: z.object({ fiscalNumber, password: anyPassword }),
  mfa: z.object({ challengeId: token, code: z.string().regex(/^\d{6}$/, "Le code contient 6 chiffres") }),
  forgot: z.object({ fiscalNumber }),
  reset: z.object({ token, newPassword: strongPassword }),
  adminSession: z.object({ password: anyPassword }),

  // Un administrateur a besoin d'un 2e mot de passe (administration), différent du 1er
  createUser: z
    .object({
      fiscalNumber,
      firstName: name,
      lastName: name,
      email: z.email("Adresse e-mail invalide").max(100),
      role: z.enum(ROLES),
      password: strongPassword,
      adminPassword: strongPassword.optional(),
    })
    .refine((d) => d.role !== "admin" || d.adminPassword, "Mot de passe d'administration obligatoire pour un administrateur")
    .refine((d) => d.adminPassword !== d.password, "Les deux mots de passe doivent être différents"),
  updateRole: z
    .object({ role: z.enum(ROLES), adminPassword: strongPassword.optional() })
    .refine((d) => d.role !== "admin" || d.adminPassword, "Mot de passe d'administration obligatoire pour un administrateur"),
  // target : "login" = mot de passe de connexion, "admin" = mot de passe d'administration
  updatePassword: z.object({ password: strongPassword, target: z.enum(["login", "admin"]).default("login") }),

  page: z.object({
    title: z.string().trim().min(1).max(80),
    description: z.string().trim().min(1).max(200),
    content: z.string().trim().min(1).max(2000),
    visible: z.boolean(),
  }),
  slug: z.string().regex(/^[a-z0-9-]{1,40}$/),
};

// Petite aide : valide et renvoie soit les données propres, soit le premier message d'erreur
export function validate<T>(schema: z.ZodType<T>, data: unknown): { data?: T; error?: string } {
  const result = schema.safeParse(data);
  if (result.success) return { data: result.data };
  return { error: result.error.issues[0]?.message || "Données invalides" };
}
