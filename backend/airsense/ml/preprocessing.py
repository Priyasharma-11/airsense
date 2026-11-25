"""Cleaning, validation and resampling of raw OpenAQ station data.

Design principles (see docs/ML_PIPELINE.md):
* Nothing is silently deleted: every rejected/flagged reading is counted in ``quality_log``.
* *Impossible* values (outside physical bounds) are removed before aggregation.
* *Flatlines* (sensor stuck >= 6 h) are removed before aggregation.
* *Statistical outliers* (rolling robust z-score) are FLAGGED but KEPT - Diwali, dust events and
  crop-burning episodes are real signal.
* 15-minute readings are averaged to hourly only when >= 50 % of slots are valid.
* Only gaps of <= 2 hours are interpolated (and marked ``pm25_imputed``); longer gaps stay NaN.
  We never manufacture observations across large gaps.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from airsense.ml.data_collection import Station, load_station_catalog, read_openaq_raw
from airsense.ml.paths import PROCESSED_DIR, REPORTS_DIR

log = logging.getLogger(__name__)

# OpenAQ parameter name -> canonical column
PARAM_MAP = {
    "pm25": "pm25", "pm10": "pm10", "no2": "no2", "so2": "so2", "co": "co", "o3": "o3",
    "no": "no", "nox": "nox", "temperature": "st_temp", "relativehumidity": "st_rh",
    "wind_speed": "st_wind_speed", "wind_direction": "st_wind_dir",
}
POLLUTANTS = ["pm25", "pm10", "no2", "so2", "co", "o3"]

# Physical plausibility bounds in CPCB reporting units (CO mg/m3, others ug/m3)
BOUNDS: dict[str, tuple[float, float]] = {
    "pm25": (0.0, 1000.0), "pm10": (0.0, 2000.0), "no2": (0.0, 1000.0), "so2": (0.0, 1000.0),
    "co": (0.0, 50.0), "o3": (0.0, 1000.0), "no": (0.0, 1500.0), "nox": (0.0, 2000.0),
    "st_temp": (-5.0, 50.0), "st_rh": (0.0, 100.0), "st_wind_speed": (0.0, 40.0), "st_wind_dir": (0.0, 360.0),
}
FLATLINE_HOURS = 6
MIN_SLOTS_PER_HOUR = 2       # of the 4 x 15-min slots
MAX_INTERP_GAP_H = 2
OUTLIER_Z = 6.0              # robust z on 24 h centred window (flag only)


@dataclass
class QualityLog:
    rows: list[dict] = field(default_factory=list)

    def add(self, station: int, param: str, check: str, n: int, action: str) -> None:
        if n:
            self.rows.append({"location_id": station, "parameter": param, "check": check, "count": int(n),
                              "action": action})

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=["location_id", "parameter", "check", "count", "action"])


def clean_station(raw: pd.DataFrame, station_id: int, qlog: QualityLog) -> tuple[pd.DataFrame, dict]:
    """Return an hourly wide frame indexed by UTC hour plus per-parameter unit labels."""
    df = raw.copy()
    df["parameter"] = df["parameter"].map(PARAM_MAP)
    df = df.dropna(subset=["parameter", "value"])
    units = df.groupby("parameter")["units"].agg(lambda s: s.mode().iloc[0]).to_dict()

    # 1) timestamps -> UTC (source strings carry +05:30 offsets)
    df["ts"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
    bad_ts = df["ts"].isna().sum()
    qlog.add(station_id, "*", "unparseable_timestamp", bad_ts, "removed")
    df = df.dropna(subset=["ts"])

    # 2) duplicates (same sensor parameter + timestamp)
    dups = df.duplicated(["parameter", "ts"], keep="last")
    qlog.add(station_id, "*", "duplicate", dups.sum(), "removed")
    df = df[~dups]

    hourly_cols = {}
    hourly_n = {}
    for param, g in df.groupby("parameter"):
        s = g.set_index("ts")["value"].sort_index().astype(float)
        lo, hi = BOUNDS.get(param, (-np.inf, np.inf))
        impossible = (s < lo) | (s > hi)
        qlog.add(station_id, param, "out_of_physical_bounds", impossible.sum(), "removed")
        s = s[~impossible]

        # flatline: identical consecutive values spanning >= FLATLINE_HOURS
        run_id = (s.diff() != 0).cumsum()
        run_start = s.index.to_series().groupby(run_id.values).transform("min")
        run_end = s.index.to_series().groupby(run_id.values).transform("max")
        flat = (run_end - run_start) >= pd.Timedelta(hours=FLATLINE_HOURS)
        flat = pd.Series(flat.values, index=s.index)
        qlog.add(station_id, param, f"flatline_>={FLATLINE_HOURS}h", flat.sum(), "removed")
        s = s[~flat]

        # hourly aggregation with slot-coverage rule
        h = s.resample("1h")
        mean, n = h.mean(), h.count()
        insufficient = (n > 0) & (n < MIN_SLOTS_PER_HOUR)
        qlog.add(station_id, param, "hour_with_<50%_slots", insufficient.sum(), "hour set to NaN")
        mean[n < MIN_SLOTS_PER_HOUR] = np.nan
        hourly_cols[param] = mean
        hourly_n[param] = n

    out = pd.DataFrame(hourly_cols)
    full_idx = pd.date_range(out.index.min(), out.index.max(), freq="1h", tz="UTC")
    out = out.reindex(full_idx)
    out.index.name = "ts"
    out["pm25_nslots"] = hourly_n.get("pm25", pd.Series(dtype=float)).reindex(full_idx).fillna(0).astype(int)

    # PM2.5 > PM10 is physically inconsistent (PM2.5 is a subset of PM10): flag only
    if {"pm25", "pm10"} <= set(out):
        incons = out["pm25"] > out["pm10"] * 1.05
        out["flag_pm25_gt_pm10"] = incons
        qlog.add(station_id, "pm25", "pm25_gt_pm10", incons.sum(), "flagged (kept)")

    # robust z-score spike flag (kept)
    for p in [c for c in POLLUTANTS if c in out]:
        med = out[p].rolling(25, center=True, min_periods=12).median()
        mad = (out[p] - med).abs().rolling(25, center=True, min_periods=12).median()
        z = 0.6745 * (out[p] - med) / mad.replace(0, np.nan)
        flag = z.abs() > OUTLIER_Z
        out[f"flag_outlier_{p}"] = flag.fillna(False)
        qlog.add(station_id, p, f"robust_z>{OUTLIER_Z}", flag.sum(), "flagged (kept)")

    # short-gap interpolation for the target only
    if "pm25" in out:
        missing = out["pm25"].isna()
        gap_id = (~missing).cumsum()
        gap_len = missing.groupby(gap_id).transform("sum")
        fillable = missing & (gap_len <= MAX_INTERP_GAP_H)
        interp = out["pm25"].interpolate(method="time", limit=MAX_INTERP_GAP_H, limit_area="inside")
        out.loc[fillable, "pm25"] = interp[fillable]
        out["pm25_imputed"] = fillable & out["pm25"].notna()
        qlog.add(station_id, "pm25", f"gap_<={MAX_INTERP_GAP_H}h_interpolated", out["pm25_imputed"].sum(),
                 "linear interpolation (marked)")

    out["location_id"] = station_id
    return out.reset_index(), units


def coverage_report(hourly: pd.DataFrame) -> pd.DataFrame:
    h = hourly.copy()
    h["month"] = h["ts"].dt.tz_convert("Asia/Kolkata").dt.strftime("%Y-%m")
    h["valid"] = h["pm25"].notna() & ~h.get("pm25_imputed", False)
    return (h.groupby(["location_id", "month"])["valid"].mean().mul(100).round(1)
              .rename("pm25_coverage_pct").reset_index())


def select_model_stations(hourly: pd.DataFrame, min_coverage: float = 70.0) -> pd.DataFrame:
    per_station = (hourly.groupby("location_id")["pm25"].apply(lambda s: s.notna().mean() * 100)
                   .round(1).rename("pm25_coverage_pct").reset_index())
    per_station["hours"] = hourly.groupby("location_id").size().values
    per_station["selected_for_model"] = per_station["pm25_coverage_pct"] >= min_coverage
    return per_station


def run(stations: list[Station] | None = None) -> dict:
    stations = stations or load_station_catalog()
    qlog = QualityLog()
    frames, units_all = [], {}
    raw_counts = {}
    for st in stations:
        raw = read_openaq_raw(st.location_id)
        raw_counts[st.location_id] = len(raw)
        if raw.empty:
            log.warning("no raw data for %s", st.name)
            continue
        hourly, units = clean_station(raw, st.location_id, qlog)
        units_all[st.location_id] = units
        frames.append(hourly)
        log.info("%-45s raw=%7d hourly=%6d pm25 valid=%.1f%%", st.name, len(raw), len(hourly),
                 hourly["pm25"].notna().mean() * 100)

    hourly = pd.concat(frames, ignore_index=True)
    # Clip analysis window to the common archive period
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "data_quality").mkdir(parents=True, exist_ok=True)
    hourly.to_parquet(PROCESSED_DIR / "hourly_measurements.parquet", index=False)
    q = qlog.frame()
    q.to_csv(REPORTS_DIR / "data_quality" / "quality_log.csv", index=False)
    cov = coverage_report(hourly)
    cov.to_csv(REPORTS_DIR / "data_quality" / "monthly_pm25_coverage.csv", index=False)
    sel = select_model_stations(hourly)
    sel.to_csv(REPORTS_DIR / "data_quality" / "station_selection.csv", index=False)
    summary = {
        "raw_rows": raw_counts,
        "hourly_rows": int(len(hourly)),
        "period_utc": [str(hourly.ts.min()), str(hourly.ts.max())],
        "units_as_labelled_by_openaq": {str(k): v for k, v in units_all.items()},
        "rules": {"bounds": BOUNDS, "flatline_hours": FLATLINE_HOURS, "min_slots_per_hour": MIN_SLOTS_PER_HOUR,
                  "max_interp_gap_h": MAX_INTERP_GAP_H, "outlier_robust_z": OUTLIER_Z},
        "station_selection": sel.to_dict(orient="records"),
    }
    (REPORTS_DIR / "data_quality" / "preprocessing_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    s = run()
    print(json.dumps(s["station_selection"], indent=1))
