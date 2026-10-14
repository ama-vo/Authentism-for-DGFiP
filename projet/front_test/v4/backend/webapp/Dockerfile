# syntax=docker/dockerfile:1
# Contexte de build : ./backend (pour inclure le module partagé common/).
FROM python:3.12-slim

WORKDIR /app

COPY webapp/requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt

COPY common ./common
COPY webapp/*.py ./

# Utilisateur non-root dédié (uid fixe : la PKI lui attribue sa clé privée).
RUN groupadd -r -g 10001 webapp && useradd -r -u 10001 -g webapp -d /app -s /usr/sbin/nologin webapp
USER 10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE_NAME=webapp \
    TLS_CA=/pki/webapp/ca.crt

EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=4s --start-period=30s --retries=6 \
    CMD ["python", "/app/common/healthcheck.py", "https://127.0.0.1:5000/health"]

# Sans état : se met à l'échelle avec `docker compose up --scale webapp=N`.
CMD ["gunicorn", "--workers", "2", "--threads", "4", "--bind", "0.0.0.0:5000", \
     "--certfile", "/pki/webapp/tls.crt", "--keyfile", "/pki/webapp/tls.key", \
     "--access-logfile", "-", "web_service:app"]
