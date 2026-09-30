# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt

COPY app.py ldap_directory.py logging_client.py store.py ./

RUN groupadd -r authsys && useradd -r -g authsys -d /app -s /sbin/nologin authsys \
    && chown -R authsys:authsys /app
USER authsys

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5001

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5001/health', timeout=2).status == 200 else 1)"

CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5001", "--access-logfile", "-", "app:app"]
