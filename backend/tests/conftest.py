"""Test configuration.

Uses a throw-away SQLite database (or AIRSENSE_TEST_DATABASE_URL, e.g. PostGIS in CI) seeded with a
slice of the REAL processed dataset (2 stations, last 21 days) and the real trained model.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="airsense-test-"))
os.environ["AIRSENSE_DATABASE_URL"] = os.environ.get("AIRSENSE_TEST_DATABASE_URL",
                                                     f"sqlite:///{(_tmp / 'test.db').as_posix()}")
os.environ["AIRSENSE_ENV"] = "development"          # enables dev_reset_token in forgot-password
os.environ["AIRSENSE_RATE_LIMIT_ENABLED"] = "false"
os.environ["AIRSENSE_SECRET_KEY"] = "test-secret-key-for-unit-tests-only-0123456789"

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from airsense.app.db.models import Base  # noqa: E402
from airsense.app.db.session import SessionLocal, get_engine  # noqa: E402
from airsense.ml.paths import INTERIM_DIR, PROCESSED_DIR  # noqa: E402

TEST_STATIONS = [3409526, 3409438]  # Panchawati_Pashan (IITM), Katraj Dairy (MPCB)


@pytest.fixture(scope="session")
def seeded():
    from airsense.app.db.models import IngestionRun, utcnow
    from airsense.app.services import forecasting, ingestion

    engine = get_engine()
    if engine.dialect.name == "postgresql":
        # Exercise the real migration path (incl. PostGIS geography column + GiST index)
        from sqlalchemy import text

        from airsense.app.cli import migrate

        with engine.begin() as c:
            c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        migrate()
    else:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
    db = SessionLocal()
    stations = ingestion.ensure_stations(db)
    run = IngestionRun(kind="seed", status="running")
    db.add(run)
    db.commit()
    hourly = pd.read_parquet(PROCESSED_DIR / "hourly_measurements.parquet")
    weather = pd.read_parquet(INTERIM_DIR / "weather_hourly.parquet")
    cutoff = hourly.ts.max() - pd.Timedelta(days=21)
    n = 0
    for loc in TEST_STATIONS:
        st = stations[loc]
        h = hourly[(hourly.location_id == loc) & (hourly.ts >= cutoff)]
        n += ingestion.upsert_measurements(db, ingestion._measurement_rows(h, st.id, run.id))
        w = weather[(weather.location_id == loc) & (weather.datetime_utc >= cutoff)]
        n += ingestion.upsert_weather(db, w, st.id)
    run.status, run.rows_upserted, run.finished_at = "success", n, utcnow()
    db.commit()
    forecasting.sync_model_registry(db)
    ids = {loc: stations[loc].id for loc in TEST_STATIONS}
    db.close()
    return ids


@pytest.fixture(scope="session")
def client(seeded):
    from airsense.app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def register_and_login(client: TestClient, email: str, password: str = "Str0ngPass!") -> dict:  # noqa: S107
    r = client.post("/api/v1/auth/register", json={"email": email, "full_name": "Test User", "password": password})
    assert r.status_code in (201, 409), r.text
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    client.cookies.clear()  # tests authenticate explicitly with the bearer token
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth_headers(client):
    import uuid

    return register_and_login(client, f"user-{uuid.uuid4().hex[:8]}@example.com")
