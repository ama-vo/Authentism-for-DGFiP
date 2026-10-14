"""Sonde HEALTHCHECK des conteneurs : GET sur l'URL donnée, en HTTPS
vérifié contre l'AC interne si TLS_CA est défini. Code 0 = sain."""
import ssl
import sys
import urllib.request
import os

url = sys.argv[1]
ctx = ssl.create_default_context(cafile=os.environ.get("TLS_CA")) if url.startswith("https") else None
try:
    with urllib.request.urlopen(url, timeout=3, context=ctx) as res:
        sys.exit(0 if res.status == 200 else 1)
except Exception:  # noqa: BLE001
    sys.exit(1)
