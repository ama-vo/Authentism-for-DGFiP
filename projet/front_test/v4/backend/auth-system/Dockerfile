# syntax=docker/dockerfile:1
# Contexte de build : ./backend (pour inclure le module partagé common/).
FROM python:3.12-slim

WORKDIR /app

COPY auth-system/requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt

COPY common ./common
COPY auth-system/*.py ./

# Utilisateur non-root dédié (uid fixe : la PKI lui attribue sa clé privée).
RUN groupadd -r -g 10002 authsys && useradd -r -u 10002 -g authsys -d /app -s /usr/sbin/nologin authsys
USER 10002

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE_NAME=auth-system \
    TLS_CA=/pki/auth-system/ca.crt

EXPOSE 5001

HEALTHCHECK --interval=10s --timeout=4s --start-period=60s --retries=6 \
    CMD ["python", "/app/common/healthcheck.py", "https://127.0.0.1:5001/health"]

# État (sessions, codes MFA) dans Redis et identités dans LDAP : les
# workers et les répliques sont sans état, on peut en ajouter librement.
# --preload : l'initialisation de l'annuaire n'est faite qu'une fois.
CMD ["gunicorn", "--preload", "--workers", "2", "--threads", "4", "--bind", "0.0.0.0:5001", \
     "--certfile", "/pki/auth-system/tls.crt", "--keyfile", "/pki/auth-system/tls.key", \
     "--access-logfile", "-", "auth_service:app"]
