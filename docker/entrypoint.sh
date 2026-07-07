#!/usr/bin/env bash
# Container entrypoint: wait for the database, apply migrations, then exec CMD.
set -euo pipefail

echo "[entrypoint] Waiting for the database to accept connections..."
python - <<'PY'
import sys
import time

from sqlalchemy import create_engine, text

from app.config.settings import get_settings

url = get_settings().sqlalchemy_database_uri
for attempt in range(1, 61):
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"[entrypoint] Database is ready (attempt {attempt}).")
        break
    except Exception as exc:  # noqa: BLE001
        print(f"[entrypoint] DB not ready ({attempt}/60): {exc}")
        time.sleep(2)
else:
    sys.exit("[entrypoint] Database never became ready; aborting.")
PY

echo "[entrypoint] Applying database migrations (alembic upgrade head)..."
alembic upgrade head

echo "[entrypoint] Starting: $*"
exec "$@"
