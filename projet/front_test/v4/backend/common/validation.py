"""
Validation stricte des entrées (cahier des charges §3.3 — résistance aux
injections). Principe : liste blanche. Chaque champ a un format attendu
précis ; tout ce qui n'y correspond pas est rejeté AVANT d'atteindre
l'annuaire LDAP, Redis ou un journal. Aucune donnée utilisateur n'est
jamais passée à un shell ni concaténée dans une requête.
"""
import re

FISCAL_ID_RE = re.compile(r"^\d{13}$")
MFA_CODE_RE = re.compile(r"^\d{6}$")
# Nom affiché : lettres (accents compris), espaces, apostrophe, tiret.
NAME_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ' \-]{1,63}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9.\-]{1,190}\.[A-Za-z]{2,24}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,31}$")
FORBIDDEN_TEXT_CHARS = set("<>{}\\`$;|&")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-]{20,128}$")

ROLES = ("external", "agent", "admin")
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128
SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")

# Endpoints réservés : une page dynamique ne peut pas les masquer.
RESERVED_SLUGS = {"login", "dashboard", "admin", "logout", "session", "password", "health", "api"}


class ValidationError(ValueError):
    pass


def is_fiscal_id(value) -> bool:
    return isinstance(value, str) and bool(FISCAL_ID_RE.fullmatch(value))


def is_mfa_code(value) -> bool:
    return isinstance(value, str) and bool(MFA_CODE_RE.fullmatch(value))


def is_token(value) -> bool:
    return isinstance(value, str) and bool(TOKEN_RE.fullmatch(value))


def password_problems(password) -> list[str]:
    """Politique du cahier des charges §2.1. Renvoie la liste des règles
    non respectées (liste vide = mot de passe conforme)."""
    if not isinstance(password, str):
        return ["format invalide"]
    problems = []
    if len(password) < PASSWORD_MIN_LENGTH:
        problems.append(f"au moins {PASSWORD_MIN_LENGTH} caractères")
    if len(password) > PASSWORD_MAX_LENGTH:
        problems.append(f"au plus {PASSWORD_MAX_LENGTH} caractères")
    if not re.search(r"[A-Z]", password):
        problems.append("une majuscule")
    if not re.search(r"[a-z]", password):
        problems.append("une minuscule")
    if not re.search(r"[0-9]", password):
        problems.append("un chiffre")
    if not SPECIAL_RE.search(password):
        problems.append("un caractère spécial")
    if any(ord(c) < 32 for c in password):
        problems.append("aucun caractère de contrôle")
    return problems


def require_password(password) -> str:
    problems = password_problems(password)
    if problems:
        raise ValidationError("Mot de passe non conforme : " + ", ".join(problems) + ".")
    return password


def require_fiscal_id(value) -> str:
    if not is_fiscal_id(value):
        raise ValidationError("Le numéro fiscal doit comporter exactement 13 chiffres.")
    return value


def require_name(value) -> str:
    if not isinstance(value, str) or not NAME_RE.fullmatch(value.strip()):
        raise ValidationError("Nom invalide (lettres, espaces, apostrophes et tirets uniquement).")
    return value.strip()


def require_email(value) -> str:
    if not isinstance(value, str) or not EMAIL_RE.fullmatch(value.strip()):
        raise ValidationError("Adresse e-mail invalide.")
    return value.strip().lower()


def require_role(value) -> str:
    if value not in ROLES:
        raise ValidationError("Rôle inconnu.")
    return value


def require_roles(values) -> list[str]:
    if not isinstance(values, list) or not values:
        raise ValidationError("Au moins un rôle doit être autorisé.")
    return sorted({require_role(v) for v in values})


def require_slug(value) -> str:
    if not isinstance(value, str) or not SLUG_RE.fullmatch(value) or value in RESERVED_SLUGS:
        raise ValidationError("Identifiant de page invalide (minuscules, chiffres, tirets ; 2 à 32 caractères).")
    return value


def require_label(value, field: str = "Libellé", max_len: int = 80) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} invalide.")
    value = value.strip()
    if (not value or len(value) > max_len or any(c in FORBIDDEN_TEXT_CHARS for c in value)
            or any(ord(c) < 32 for c in value)):
        raise ValidationError(f"{field} invalide (caractères spéciaux < > {{ }} \\ ` $ ; | & interdits).")
    return value


def bounded_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, n))
