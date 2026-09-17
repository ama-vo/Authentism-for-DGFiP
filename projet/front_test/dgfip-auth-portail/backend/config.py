import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration centrale de l'API. Toutes les valeurs sensibles
    proviennent des variables d'environnement — ne jamais coder en dur
    de secret ici."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-not-for-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///dgfip_auth.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")

    # Politique de mot de passe (cahier des charges §2.1)
    PASSWORD_MIN_LENGTH = 12

    # Durée de vie des jetons de session (§2.2 / §2.3)
    NORMAL_SESSION_LIFETIME = timedelta(hours=2)
    ADMIN_SESSION_LIFETIME = timedelta(minutes=10)

    # Double authentification (§2.1)
    MFA_CODE_LIFETIME = timedelta(minutes=5)
    MFA_MAX_ATTEMPTS = 3

    # Limitation de débit — première ligne de défense contre le
    # bourrage de force brute, en complément de la répartition de
    # charge / file d'attente gérée au niveau infrastructure (§3.1)
    LOGIN_RATE_LIMIT = "10 per minute"
    MFA_RATE_LIMIT = "10 per minute"

    # Ne JAMAIS activer en production : sert uniquement à tester le
    # parcours MFA localement sans expéditeur d'e-mail réel.
    DEBUG_EXPOSE_MFA_CODE = os.environ.get("DEBUG_EXPOSE_MFA_CODE", "false").lower() == "true"
