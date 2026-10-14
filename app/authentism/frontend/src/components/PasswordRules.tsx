// Affiche en direct les règles du mot de passe (mêmes règles que le serveur)

export const PASSWORD_RULES = [
  { label: "12 caractères minimum", test: (p: string) => p.length >= 12 },
  { label: "Une majuscule", test: (p: string) => /[A-Z]/.test(p) },
  { label: "Une minuscule", test: (p: string) => /[a-z]/.test(p) },
  { label: "Un chiffre", test: (p: string) => /[0-9]/.test(p) },
  { label: "Un caractère spécial", test: (p: string) => /[^A-Za-z0-9]/.test(p) },
];

export const isStrongPassword = (password: string) => PASSWORD_RULES.every((rule) => rule.test(password));

export default function PasswordRules({ password }: { password: string }) {
  return (
    <ul className="rules">
      {PASSWORD_RULES.map((rule) => (
        <li key={rule.label} className={rule.test(password) ? "ok" : ""}>
          {rule.test(password) ? "✓" : "•"} {rule.label}
        </li>
      ))}
    </ul>
  );
}
