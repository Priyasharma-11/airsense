#!/bin/sh
# Apply migrations, seed the database on first boot, then serve.
set -e
python -m airsense.app.cli migrate
if [ "${AIRSENSE_SEED_ON_START:-true}" = "true" ]; then
  python - <<'PY'
from sqlalchemy import func, select
from airsense.app.db.models import Measurement
from airsense.app.db.session import SessionLocal
db = SessionLocal()
empty = (db.scalar(select(func.count(Measurement.id))) or 0) == 0
db.close()
if empty:
    from airsense.app.cli import main
    print("database empty - seeding from processed pipeline output")
    main(["seed"])
PY
fi
exec uvicorn airsense.app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" --proxy-headers --forwarded-allow-ips="*"
