"""
Flux 4 : envoi du code de validation à l'adresse e-mail du compte.

En Docker, les e-mails partent vers Mailpit (serveur SMTP de test dont
l'interface web permet de lire les messages reçus). En production, on
pointerait SMTP_HOST vers le relais de messagerie de la DGFiP.
Sans SMTP_HOST, le message est seulement écrit dans les logs du service
(développement local).
"""
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "1025"))
SMTP_STARTTLS = os.environ.get("SMTP_STARTTLS", "false").lower() == "true"
SMTP_FROM = os.environ.get("SMTP_FROM", "no-reply@dgfip.example")
TLS_CA = os.environ.get("TLS_CA")

logger = logging.getLogger("mailer")

SUBJECTS = {
    "login": "Votre code de connexion",
    "reset": "Réinitialisation de votre mot de passe",
}
INTROS = {
    "login": "Voici votre code de vérification pour vous connecter au portail DGFiP",
    "reset": "Voici votre code pour réinitialiser votre mot de passe sur le portail DGFiP",
}


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    return f"{local[:1]}***@{domain}"


def send_code(email: str, name: str, code: str, purpose: str, ttl_seconds: int) -> None:
    msg = EmailMessage()
    msg["Subject"] = f"[DGFiP] {SUBJECTS[purpose]}"
    msg["From"] = SMTP_FROM
    msg["To"] = email
    msg.set_content(
        f"Bonjour {name},\n\n{INTROS[purpose]} :\n\n    {code}\n\n"
        f"Ce code expire dans {ttl_seconds // 60} minutes et ne peut être utilisé qu'une seule fois.\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message et prévenez votre "
        "service informatique.\n\nDGFiP — message automatique, ne pas répondre."
    )
    if not SMTP_HOST:
        logger.warning("[DEV] e-mail non envoyé (SMTP_HOST vide) — %s → %s : code %s", purpose, email, code)
        return
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5) as smtp:
            if SMTP_STARTTLS:
                ctx = ssl.create_default_context(cafile=TLS_CA) if TLS_CA else ssl.create_default_context()
                smtp.starttls(context=ctx)
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException) as exc:
        logger.error("Échec d'envoi de l'e-mail à %s : %s", mask_email(email), exc)
        raise
