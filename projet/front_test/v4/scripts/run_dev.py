"""
Lance les trois services backend SANS Docker, pour le développement :
annuaire LDAP simulé en mémoire, Redis en mémoire, HTTP sans TLS, code
2FA renvoyé dans la réponse (DEBUG_EXPOSE_MFA_CODE).

    pip install -r backend/requirements-dev.txt
    python scripts/run_dev.py
    # puis, dans un autre terminal : cd frontend && npm install && npm run dev
    # -> http://localhost:5173 (Vite relaie /api vers webapp:5000)

Ctrl+C arrête les trois services.
"""
import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND = os.path.join(ROOT, "backend")

COMMON = {
    "APP_ENV": "dev",
    "INTERNAL_SHARED_SECRETS": "dev-internal-secret-change-me",
    "LOG_COLLECTOR_URL": "http://127.0.0.1:5002",
    "PYTHONUNBUFFERED": "1",
    "PYTHONIOENCODING": "utf-8",
}
SERVICES = [
    ("log-collector", "log_service.py", {"SERVICE_NAME": "log-collector",
                                         "LOG_DB_PATH": os.path.join(BACKEND, "log-collector", "events.jsonl")}),
    ("auth-system", "auth_service.py", {"SERVICE_NAME": "auth-system", "LDAP_MODE": "mock", "REDIS_URL": "memory://",
                                        "DEBUG_EXPOSE_MFA_CODE": "true", "PASSWORD_HASH_ROUNDS": "50000"}),
    ("webapp", "web_service.py", {"SERVICE_NAME": "webapp", "AUTH_SYSTEM_URL": "http://127.0.0.1:5001",
                                  "COOKIE_SECURE": "false", "TRUST_PROXY": "false"}),
]


def main() -> int:
    procs = []
    try:
        for name, script, env in SERVICES:
            full_env = {**os.environ, **COMMON, **env}
            procs.append(subprocess.Popen([sys.executable, script], cwd=os.path.join(BACKEND, name), env=full_env))
            print(f"[dev] {name} démarré")
            time.sleep(1.5)
        print("[dev] webapp : http://127.0.0.1:5000  (frontend : cd frontend && npm run dev)")
        while all(p.poll() is None for p in procs):
            time.sleep(1)
        print("[dev] un service s'est arrêté.")
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    sys.exit(main())
