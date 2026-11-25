"""Loading data into the database: one-off seed from the processed pipeline output, and incremental
sync from OpenAQ + Open-Meteo. Upserts are idempotent (ON CONFLICT DO UPDATE on both SQLite & Postgres)."""
from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from airsense.app.db.models import DataSource, IngestionRun, Measurement, Station, WeatherObservation, utcnow
from airsense.app.services.data import UNITS, clear_cache
from airsense.ml import data_collection as dc
from airsense.ml import preprocessing as pp
from airsense.ml.paths import INTERIM_DIR, PROCESSED_DIR, REPORTS_DIR

log = logging.getLogger(__name__)
_sync_lock = threading.Lock()

SOURCES = [
    dict(slug="openaq", name="OpenAQ (CPCB / MPCB / IITM CAAQMS stations)", kind="observation", license="CC BY 4.0",
         url="https://openaq.org", description="Station measurements via the OpenAQ open-data archive on AWS."),
    dict(slug="open-meteo-era5", name="Open-Meteo Historical Weather (ERA5 reanalysis)", kind="reanalysis",
         license="CC BY 4.0", url="https://open-meteo.com/en/docs/historical-weather-api",
         description="Hourly weather at each station coordinate."),
    dict(slug="cams", name="Copernicus CAMS global forecast (via Open-Meteo)", kind="model_benchmark",
         license="CC BY 4.0", url="https://open-meteo.com/en/docs/air-quality-api",
         description="Physics-based model PM2.5 used ONLY as an evaluation benchmark."),
]
WEATHER_COLS = ["temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m", "wind_direction_10m",
                "surface_pressure", "boundary_layer_height"]


def _insert(db: Session, table):
    return (postgresql.insert if db.get_bind().dialect.name == "postgresql" else sqlite.insert)(table)


def ensure_sources(db: Session) -> dict[str, DataSource]:
    out = {}
    for s in SOURCES:
        row = db.scalar(select(DataSource).where(DataSource.slug == s["slug"]))
        if row is None:
            row = DataSource(**s)
            db.add(row)
        out[s["slug"]] = row
    db.commit()
    return out


def ensure_stations(db: Session) -> dict[int, Station]:
    src = ensure_sources(db)["openaq"]
    sel_path = REPORTS_DIR / "data_quality" / "station_selection.csv"
    sel = pd.read_csv(sel_path).set_index("location_id") if sel_path.exists() else pd.DataFrame()
    out = {}
    for s in dc.load_station_catalog():
        row = db.scalar(select(Station).where(Station.source_id == src.id, Station.external_id == str(s.location_id)))
        if row is None:
            row = Station(source_id=src.id, external_id=str(s.location_id))
            db.add(row)
        row.name, row.city, row.provider = s.name, s.city, s.provider
        row.latitude, row.longitude = s.latitude, s.longitude
        if s.first_seen:
            row.first_seen = datetime.strptime(s.first_seen, "%Y%m%d").replace(tzinfo=UTC)
        if s.location_id in sel.index:
            row.used_in_model = bool(sel.loc[s.location_id, "selected_for_model"])
            row.pm25_coverage_pct = float(sel.loc[s.location_id, "pm25_coverage_pct"])
        out[s.location_id] = row
    db.commit()
    return out


def _measurement_rows(hourly: pd.DataFrame, station_db_id: int, run_id: int) -> list[dict]:
    rows = []
    for p in UNITS:
        if p not in hourly:
            continue
        d = hourly[["ts", p] + [c for c in (f"flag_outlier_{p}",) if c in hourly]].dropna(subset=[p])
        d = d[d[p] >= 0]
        imputed = hourly.loc[d.index, "pm25_imputed"].fillna(False).values if p == "pm25" and "pm25_imputed" in hourly \
            else np.zeros(len(d), bool)
        outl = d[f"flag_outlier_{p}"].fillna(False).values if f"flag_outlier_{p}" in d else np.zeros(len(d), bool)
        for ts, v, imp, o in zip(d["ts"], d[p].values, imputed, outl):
            rows.append({"station_id": station_db_id, "ts": ts.to_pydatetime(), "parameter": p, "value": float(v),
                         "unit": UNITS[p], "is_imputed": bool(imp), "is_outlier": bool(o), "ingestion_run_id": run_id})
    return rows


def upsert_measurements(db: Session, rows: list[dict], chunk: int = 3500) -> int:  # 8 cols x 3500 < SQLite 32766 vars
    for i in range(0, len(rows), chunk):
        stmt = _insert(db, Measurement).values(rows[i:i + chunk])
        stmt = stmt.on_conflict_do_update(index_elements=["station_id", "parameter", "ts"],
                                          set_={"value": stmt.excluded.value, "is_imputed": stmt.excluded.is_imputed,
                                                "is_outlier": stmt.excluded.is_outlier,
                                                "ingestion_run_id": stmt.excluded.ingestion_run_id})
        db.execute(stmt)
    db.commit()
    return len(rows)


def upsert_weather(db: Session, w: pd.DataFrame, station_db_id: int) -> int:
    rows = [{"station_id": station_db_id, "ts": r.datetime_utc.to_pydatetime(),
             **{c: (None if pd.isna(getattr(r, c)) else float(getattr(r, c))) for c in WEATHER_COLS},
             "source_tag": r.weather_source} for r in w.itertuples()]
    for i in range(0, len(rows), 2500):  # 11 cols x 2500 < SQLite variable limit
        stmt = _insert(db, WeatherObservation).values(rows[i:i + 2500])
        stmt = stmt.on_conflict_do_update(index_elements=["station_id", "ts"],
                                          set_={c: getattr(stmt.excluded, c) for c in WEATHER_COLS + ["source_tag"]})
        db.execute(stmt)
    db.commit()
    return len(rows)


def _start_run(db: Session, kind: str, user_id: int | None) -> IngestionRun:
    run = IngestionRun(kind=kind, status="running", triggered_by_id=user_id,
                       source_id=ensure_sources(db)["openaq"].id)
    db.add(run)
    db.commit()
    return run


def seed_from_pipeline(db: Session) -> IngestionRun:
    """Load the processed dataset produced by airsense.ml.preprocessing into the database."""
    stations = ensure_stations(db)
    run = _start_run(db, "seed", None)
    try:
        hourly = pd.read_parquet(PROCESSED_DIR / "hourly_measurements.parquet")
        weather = pd.read_parquet(INTERIM_DIR / "weather_hourly.parquet")
        total = 0
        for loc_id, st in stations.items():
            h = hourly[hourly.location_id == loc_id]
            total += upsert_measurements(db, _measurement_rows(h, st.id, run.id))
            total += upsert_weather(db, weather[weather.location_id == loc_id], st.id)
            log.info("seeded %s", st.name)
        run.status, run.rows_upserted, run.finished_at = "success", total, utcnow()
        run.details = {"source": "data/processed/hourly_measurements.parquet + data/interim/weather_hourly.parquet"}
    except Exception as e:
        run.status, run.finished_at, run.details = "failed", utcnow(), {"error": str(e)}
        db.commit()
        raise
    db.commit()
    clear_cache()
    return run


def incremental_sync(db: Session, days: int = 7, user_id: int | None = None) -> IngestionRun:
    """Fetch the most recent ``days`` of data from the sources and upsert it."""
    if not _sync_lock.acquire(blocking=False):
        raise RuntimeError("An ingestion run is already in progress.")
    run = _start_run(db, "incremental", user_id)
    details: dict = {"days": days, "stations": {}}
    try:
        stations = ensure_stations(db)
        since = date.today() - timedelta(days=days)
        margin = since - timedelta(days=2)   # context for flatline / outlier windows
        total = 0
        for loc_id, st in stations.items():
            stats = dc.download_openaq_archive(loc_id, start=margin)
            raw = dc.read_openaq_raw(loc_id, since=margin)
            entry = {"archive": stats, "rows": 0}
            if not raw.empty:
                qlog = pp.QualityLog()
                hourly, _ = pp.clean_station(raw, loc_id, qlog)
                hourly = hourly[hourly.ts >= pd.Timestamp(since, tz="UTC")]
                n = upsert_measurements(db, _measurement_rows(hourly, st.id, run.id))
                entry["rows"] = n
                entry["quality"] = qlog.frame().groupby("check")["count"].sum().to_dict()
                total += n
            try:
                w = dc.download_weather(dc.Station(loc_id, st.name, st.latitude, st.longitude, st.provider, st.city),
                                        margin, date.today())
                total += upsert_weather(db, w, st.id)
            except dc.FetchError as e:
                entry["weather_error"] = str(e)
            details["stations"][str(loc_id)] = entry
        run.status, run.rows_upserted, run.finished_at, run.details = "success", total, utcnow(), details
        db.commit()
        clear_cache()
        from airsense.app.services import alerting  # local import avoids a cycle
        _, created = alerting.evaluate_rules(db)
        run.details = {**details, "alerts_created": len(created)}
        db.commit()
    except Exception as e:
        db.rollback()
        run.status, run.finished_at = "failed", utcnow()
        run.details = {**details, "error": str(e)}
        db.commit()
        log.exception("incremental sync failed")
    finally:
        _sync_lock.release()
    return run


def json_safe(o):
    return json.loads(json.dumps(o, default=str))
