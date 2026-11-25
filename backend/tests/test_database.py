"""Database tests: migrations, constraints, idempotent upserts, timezone handling."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from airsense.app.db.models import Measurement, Station, User
from airsense.app.db.session import SessionLocal
from airsense.app.services import ingestion

BACKEND = Path(__file__).resolve().parents[1]


def test_alembic_upgrade_downgrade_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        env = {**os.environ, "AIRSENSE_DATABASE_URL": f"sqlite:///{Path(d, 'm.db').as_posix()}", "PYTHONPATH": str(BACKEND)}
        for cmd in (["upgrade", "head"], ["downgrade", "base"], ["upgrade", "head"]):
            r = subprocess.run([sys.executable, "-m", "alembic", *cmd], cwd=BACKEND, env=env, capture_output=True, text=True)
            assert r.returncode == 0, r.stderr


def test_measurement_constraints(seeded):
    db = SessionLocal()
    sid = next(iter(seeded.values()))
    ts = datetime(2020, 1, 1, tzinfo=UTC)
    db.add(Measurement(station_id=sid, ts=ts, parameter="pm25", value=-1, unit="µg/m³"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(Measurement(station_id=sid, ts=ts, parameter="benzene", value=1, unit="µg/m³"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(Measurement(station_id=999999, ts=ts, parameter="pm25", value=1, unit="µg/m³"))
    with pytest.raises(IntegrityError):   # foreign key enforced
        db.commit()
    db.rollback()
    db.close()


def test_upsert_is_idempotent_and_updates(seeded):
    db = SessionLocal()
    sid = next(iter(seeded.values()))
    ts = datetime(2021, 6, 1, 12, tzinfo=UTC)
    row = {"station_id": sid, "ts": ts, "parameter": "pm25", "value": 10.0, "unit": "µg/m³", "is_imputed": False,
           "is_outlier": False, "ingestion_run_id": None}
    ingestion.upsert_measurements(db, [row])
    ingestion.upsert_measurements(db, [{**row, "value": 12.5}])
    rows = db.execute(select(Measurement).where(Measurement.station_id == sid, Measurement.ts == ts)).scalars().all()
    assert len(rows) == 1 and rows[0].value == 12.5
    assert rows[0].ts.tzinfo is not None and rows[0].ts == ts   # UTC preserved even on SQLite
    db.delete(rows[0])
    db.commit()
    db.close()


def test_unique_email(seeded):
    db = SessionLocal()
    db.add_all([User(email="same@example.com", full_name="A", hashed_password="x"),
                User(email="same@example.com", full_name="B", hashed_password="y")])
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


def test_station_catalog_loaded(seeded):
    db = SessionLocal()
    assert db.scalar(select(func.count(Station.id))) == 10
    assert db.scalar(select(func.count(Station.id)).where(Station.used_in_model)) == 8
    db.close()
