# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt

COPY app.py ./

RUN groupadd -r logcollector && useradd -r -g logcollector -d /app -s /sbin/nologin logcollector \
    && mkdir -p /data \
    && chown -R logcollector:logcollector /app /data
USER logcollector

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5002 \
    LOG_DB_PATH=/data/events.jsonl

# /data est destiné à être monté en volume nommé (persistance des
# événements au-delà du cycle de vie du conteneur).
VOLUME ["/data"]

EXPOSE 5002

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5002/health', timeout=2).status == 200 else 1)"

CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5002", "--access-logfile", "-", "app:app"]
