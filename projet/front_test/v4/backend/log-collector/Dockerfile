# syntax=docker/dockerfile:1
# Contexte de build : ./backend (pour inclure le module partagé common/).
FROM python:3.12-slim

WORKDIR /app

COPY log-collector/requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt

COPY common ./common
COPY log-collector/*.py ./

# Utilisateur non-root dédié (uid fixe : la PKI lui attribue sa clé privée).
RUN groupadd -r -g 10003 logs && useradd -r -u 10003 -g logs -d /app -s /usr/sbin/nologin logs \
    && mkdir -p /data && chown 10003:10003 /data
VOLUME ["/data"]
USER 10003

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVICE_NAME=log-collector \
    TLS_CA=/pki/log-collector/ca.crt \
    LOG_DB_PATH=/data/events.jsonl

EXPOSE 5002

HEALTHCHECK --interval=10s --timeout=4s --start-period=30s --retries=6 \
    CMD ["python", "/app/common/healthcheck.py", "https://127.0.0.1:5002/health"]

# Un seul worker : la chaîne d'intégrité HMAC des journaux est
# sérialisée par un verrou en mémoire (8 threads pour la concurrence).
# HTTPS interne : certificat délivré par la PKI (service "pki").
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--bind", "0.0.0.0:5002", \
     "--certfile", "/pki/log-collector/tls.crt", "--keyfile", "/pki/log-collector/tls.key", \
     "--access-logfile", "-", "log_service:app"]
