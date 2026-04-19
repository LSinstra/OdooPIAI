#!/usr/bin/env bash
set -euo pipefail

# Wait for Postgres (depends_on health should cover it, but be defensive).
python - <<'PY'
import os, time, socket
host = os.environ.get("POSTGRES_HOST", "db")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
deadline = time.time() + 60
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=2):
            print(f"postgres at {host}:{port} is up")
            break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit(f"postgres at {host}:{port} unreachable after 60s")
PY

# Apply migrations (Alembic uses env.py which imports our models metadata).
alembic upgrade head

exec "$@"
