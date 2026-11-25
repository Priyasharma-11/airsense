"""Data-access helpers that turn DB rows into pandas frames, with a small invalidating cache.

The cache key includes the id of the latest successful ingestion run, so any new data written by
the ingestion service invalidates analytics automatically.
"""
from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from airsense.app.core.errors import NotFound
from airsense.app.db.models import IngestionRun, Measurement, Station, WeatherObservation

UNITS = {"pm25": "µg/m³", "pm10": "µg/m³", "no2": "µg/m³", "so2": "µg/m³", "o3": "µg/m³", "co": "mg/m³"}
IST = "Asia/Kolkata"

_cache: dict[tuple, tuple[float, object]] = {}
_lock = threading.Lock()
TTL_SECONDS = 600


def data_version(db: Session) -> int:
    return db.scalar(select(func.max(IngestionRun.id)).where(IngestionRun.status == "success")) or 0


_key_locks: dict[tuple, threading.Lock] = {}


def cached(db: Session, key: tuple, fn):
    """TTL cache with single-flight semantics: concurrent requests for the same key wait for one
    computation instead of each rebuilding the same frame (important on a cold start)."""
    full = (data_version(db), *key)

    def fresh():
        hit = _cache.get(full)
        return hit[1] if hit and time.time() - hit[0] < TTL_SECONDS else None

    with _lock:
        val = fresh()
        if val is not None:
            return val
        klock = _key_locks.setdefault(full, threading.Lock())
    with klock:
        with _lock:
            val = fresh()
        if val is not None:
            return val
        val = fn()
        with _lock:
            if len(_cache) > 256:
                _cache.clear()
                _key_locks.clear()
            _cache[full] = (time.time(), val)
        return val


def warm_cache() -> None:
    """Pre-compute the heavy analytics frames (called in a background thread at startup)."""
    from airsense.app.db.session import SessionLocal
    from airsense.app.services import analytics, measurements

    db = SessionLocal()
    try:
        wide_all(db)
        weather_all(db)
        measurements.latest_all(db)
        analytics.summary(db)
        analytics.insights(db)
    finally:
        db.close()


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def get_station(db: Session, station_id: int) -> Station:
    st = db.get(Station, station_id)
    if st is None:
        raise NotFound(f"Station {station_id} not found.")
    return st


def _to_utc(s: pd.Series) -> pd.Series:
    s = pd.to_datetime(s)
    return s.dt.tz_localize("UTC") if s.dt.tz is None else s.dt.tz_convert("UTC")


def measurements_long(db: Session, station_ids: list[int] | None = None, parameters: list[str] | None = None,
                      start: datetime | None = None, end: datetime | None = None) -> pd.DataFrame:
    q = select(Measurement.station_id, Measurement.ts, Measurement.parameter, Measurement.value,
               Measurement.is_imputed, Measurement.is_outlier)
    if station_ids:
        q = q.where(Measurement.station_id.in_(station_ids))
    if parameters:
        q = q.where(Measurement.parameter.in_(parameters))
    if start:
        q = q.where(Measurement.ts >= start)
    if end:
        q = q.where(Measurement.ts <= end)
    rows = db.execute(q).all()
    df = pd.DataFrame(rows, columns=["station_id", "ts", "parameter", "value", "is_imputed", "is_outlier"])
    if len(df):
        df["ts"] = _to_utc(df["ts"])
    return df


def wide_all(db: Session) -> pd.DataFrame:
    """All stations, all pollutants, hourly wide frame (cached)."""
    def build():
        df = measurements_long(db)
        if df.empty:
            return pd.DataFrame(columns=["station_id", "ts", *UNITS])
        w = df.pivot_table(index=["station_id", "ts"], columns="parameter", values="value").reset_index()
        w.columns.name = None
        return w
    return cached(db, ("wide_all",), build)


def weather_all(db: Session) -> pd.DataFrame:
    def build():
        rows = db.execute(select(WeatherObservation)).scalars().all()
        df = pd.DataFrame([{c: getattr(r, c) for c in ("station_id", "ts", "temperature_2m", "relative_humidity_2m",
                                                        "precipitation", "wind_speed_10m", "wind_direction_10m",
                                                        "surface_pressure", "boundary_layer_height")} for r in rows])
        if len(df):
            df["ts"] = _to_utc(df["ts"])
        return df
    return cached(db, ("weather_all",), build)


def station_hourly(db: Session, station_id: int, hours: int = 24 * 9, end: datetime | None = None) -> pd.DataFrame:
    """Wide hourly frame for one station in the format expected by the ML feature builder."""
    end = end or db.scalar(select(func.max(Measurement.ts)).where(Measurement.station_id == station_id))
    if end is None:
        return pd.DataFrame()
    start = end - timedelta(hours=hours)
    df = measurements_long(db, [station_id], start=start, end=end)
    if df.empty:
        return pd.DataFrame()
    w = df.pivot_table(index="ts", columns="parameter", values="value").reset_index()
    w.columns.name = None
    imp = df[df.parameter == "pm25"].set_index("ts")["is_imputed"]
    w["pm25_imputed"] = w["ts"].map(imp).fillna(False).astype(bool)
    w["location_id"] = station_id
    return w


def station_weather(db: Session, station_id: int, start: datetime, end: datetime) -> pd.DataFrame:
    rows = db.execute(select(WeatherObservation).where(WeatherObservation.station_id == station_id,
                                                       WeatherObservation.ts >= start,
                                                       WeatherObservation.ts <= end)).scalars().all()
    df = pd.DataFrame([{"datetime_utc": r.ts, "temperature_2m": r.temperature_2m,
                        "relative_humidity_2m": r.relative_humidity_2m, "precipitation": r.precipitation,
                        "wind_speed_10m": r.wind_speed_10m, "wind_direction_10m": r.wind_direction_10m,
                        "surface_pressure": r.surface_pressure, "boundary_layer_height": r.boundary_layer_height}
                       for r in rows])
    if len(df):
        df["datetime_utc"] = _to_utc(df["datetime_utc"])
    return df


def resample(series: pd.DataFrame, resolution: str) -> pd.DataFrame:
    """series: ts (UTC), value -> aggregated in IST calendar buckets with count."""
    if series.empty:
        return pd.DataFrame(columns=["ts", "value", "n"])
    s = series.set_index("ts")["value"].tz_convert(IST)
    if resolution == "hour":
        out = s.to_frame("value")
        out["n"] = 1
    else:
        rule = "1D" if resolution == "day" else "MS"
        g = s.resample(rule)
        out = pd.DataFrame({"value": g.mean(), "n": g.count()})
        min_n = 18 if resolution == "day" else 24 * 10   # completeness rule for daily / monthly means
        out.loc[out["n"] < min_n, "value"] = np.nan
    out.index = out.index.tz_convert("UTC")
    return out.reset_index().rename(columns={"index": "ts"})


def nan_to_none(x):
    if x is None:
        return None
    try:
        return None if np.isnan(x) else float(x)
    except TypeError:
        return x


def now_utc() -> datetime:
    return datetime.now(UTC)
