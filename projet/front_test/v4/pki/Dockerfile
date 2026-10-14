# syntax=docker/dockerfile:1
# Service ponctuel : génère/renouvelle les certificats puis s'arrête.
FROM python:3.12-slim
RUN pip install --no-cache-dir --no-compile cryptography==43.0.1
COPY generate.py /generate.py
ENV PYTHONUNBUFFERED=1
CMD ["python", "/generate.py"]
