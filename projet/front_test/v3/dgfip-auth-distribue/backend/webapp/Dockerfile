# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt

COPY app.py auth_client.py ./

# Utilisateur non-root dédié — jamais root en conteneur.
RUN groupadd -r webapp && useradd -r -g webapp -d /app -s /sbin/nologin webapp \
    && chown -R webapp:webapp /app
USER webapp

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2).status == 200 else 1)"

# 2 workers suffisent pour ce prototype ; ajuster selon la charge réelle.
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", "--access-logfile", "-", "app:app"]
