import { passwordRules } from "../utils/validation";

const LABELS: Record<keyof ReturnType<typeof passwordRules>, string> = {
  length: "12 caractères minimum",
  uppercase: "Une majuscule",
  lowercase: "Une minuscule",
  digit: "Un chiffre",
  special: "Un caractère spécial",
};

export function PasswordChecklist({ password }: { password: string }) {
  const rules = passwordRules(password);
  return (
    <ul className="pw-checklist">
      {(Object.keys(LABELS) as Array<keyof typeof LABELS>).map((key) => (
        <li key={key} className={rules[key] ? "ok" : ""}>
          <span className="dot" />
          {LABELS[key]}
        </li>
      ))}
    </ul>
  );
}
