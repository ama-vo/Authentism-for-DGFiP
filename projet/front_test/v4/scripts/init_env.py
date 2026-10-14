"""Crée le fichier .env à partir de .env.example en générant des secrets
aléatoires robustes. Ne modifie pas un .env existant (sauf --force).

    python scripts/init_env.py
"""
import os
import secrets
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXAMPLE, TARGET = os.path.join(ROOT, ".env.example"), os.path.join(ROOT, ".env")
GENERATED = ("INTERNAL_SHARED_SECRETS", "LOG_SIGNING_KEY", "LDAP_ADMIN_PASSWORD",
             "LDAP_CONFIG_PASSWORD", "REDIS_PASSWORD")

if os.path.exists(TARGET) and "--force" not in sys.argv:
    print(".env existe déjà — rien à faire (utilisez --force pour le régénérer).")
    sys.exit(0)

lines = []
with open(EXAMPLE, encoding="utf-8") as f:
    for line in f:
        key = line.split("=", 1)[0].strip()
        if key in GENERATED and line.strip().endswith("="):
            line = f"{key}={secrets.token_hex(32)}\n"
        lines.append(line)

with open(TARGET, "w", encoding="utf-8", newline="\n") as f:
    f.writelines(lines)
print(".env créé avec des secrets aléatoires.")
