"""Leakage-safe feature engineering for direct multi-horizon PM2.5 forecasting.

Convention
----------
A row is an *issue time* ``t`` (the last hour whose observations are known). For horizon ``h`` the
target is ``pm25(t + h)``. Every feature is computed from data at or before ``t`` - except calendar
features of the *target* time, which are known in advance (hour of day, weekday, festival dates).

The same ``build_features`` function is used for training and for live inference in the API,
which guarantees train/serve consistency.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TARGET = "pm25"
PM25_LAGS = [1, 2, 3, 6, 12, 24, 48, 168]
ROLL_WINDOWS = [3, 6, 12, 24]
HORIZONS = list(range(1, 25))
IST = "Asia/Kolkata"

# Diwali (Lakshmi Puja) +/- 2 days. Dates: Govt. of India holiday calendars 2025-2026.
FESTIVAL_WINDOWS = [
    ("2025-10-18", "2025-10-24"),
    ("2026-11-06", "2026-11-12"),
]

WEATHER_COLS = ["temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m",
                "wind_direction_10m", "surface_pressure", "boundary_layer_height"]
AUX_POLLUTANTS = ["pm10", "no2", "so2", "co", "o3"]

# India - Monsoon-aware seasons as used by IMD
SEASON_OF_MONTH = {12: "winter", 1: "winter", 2: "winter", 3: "summer", 4: "summer", 5: "summer",
                   6: "monsoon", 7: "monsoon", 8: "monsoon", 9: "monsoon", 10: "post_monsoon",
                   11: "post_monsoon"}
SEASONS = ["winter", "summer", "monsoon", "post_monsoon"]


def is_festival(ts_local: pd.Series) -> pd.Series:
    d = ts_local.dt.tz_localize(None).dt.normalize()
    flag = pd.Series(False, index=ts_local.index)
    for a, b in FESTIVAL_WINDOWS:
        flag |= d.between(pd.Timestamp(a), pd.Timestamp(b))
    return flag


def _calendar(ts_utc: pd.Series, prefix: str) -> pd.DataFrame:
    loc = ts_utc.dt.tz_convert(IST)
    hour, dow, month = loc.dt.hour, loc.dt.day_of_week, loc.dt.month
    out = pd.DataFrame(index=ts_utc.index)
    out[f"{prefix}hour_sin"] = np.sin(2 * np.pi * hour / 24)
    out[f"{prefix}hour_cos"] = np.cos(2 * np.pi * hour / 24)
    out[f"{prefix}dow"] = dow
    out[f"{prefix}is_weekend"] = (dow >= 5).astype(int)
    out[f"{prefix}month_sin"] = np.sin(2 * np.pi * month / 12)
    out[f"{prefix}month_cos"] = np.cos(2 * np.pi * month / 12)
    season = month.map(SEASON_OF_MONTH)
    for s in SEASONS:
        out[f"{prefix}season_{s}"] = (season == s).astype(int)
    out[f"{prefix}is_festival"] = is_festival(loc).astype(int)
    return out


def build_features(hourly: pd.DataFrame, weather: pd.DataFrame | None = None) -> pd.DataFrame:
    """Features at every issue time for ONE station.

    ``hourly``: columns ts (UTC, hourly, contiguous or not), pm25, pm10, no2, so2, co, o3, location_id
    ``weather``: columns datetime_utc + WEATHER_COLS (optional)
    """
    df = hourly.sort_values("ts").set_index("ts")
    full = pd.date_range(df.index.min(), df.index.max(), freq="1h", tz="UTC")
    df = df.reindex(full)
    df.index.name = "ts"
    y = df[TARGET].astype(float)

    f = pd.DataFrame(index=df.index)
    f["pm25_lag0"] = y
    for L in PM25_LAGS:
        f[f"pm25_lag{L}"] = y.shift(L)
    for w in ROLL_WINDOWS:
        r = y.rolling(w, min_periods=max(2, w // 2))
        f[f"pm25_rmean{w}"] = r.mean()
        f[f"pm25_rstd{w}"] = r.std()
    f["pm25_rmax24"] = y.rolling(24, min_periods=12).max()
    f["pm25_rmin24"] = y.rolling(24, min_periods=12).min()
    f["pm25_diff1"] = y - y.shift(1)
    f["pm25_diff24"] = y - y.shift(24)
    f["pm25_rmean168"] = y.rolling(168, min_periods=84).mean()
    f["pm25_missing_24h"] = y.isna().rolling(24, min_periods=1).sum()

    for p in AUX_POLLUTANTS:
        if p in df:
            s = df[p].astype(float)
            f[f"{p}_lag0"] = s
            f[f"{p}_rmean24"] = s.rolling(24, min_periods=12).mean()
    if {"pm10"} <= set(df):
        f["pm_ratio_rmean24"] = (y.rolling(24, min_periods=12).mean()
                                 / df["pm10"].astype(float).rolling(24, min_periods=12).mean())

    if weather is not None and len(weather):
        w = weather.set_index("datetime_utc").sort_index()
        w = w[~w.index.duplicated()].reindex(df.index)
        for c in WEATHER_COLS:
            if c in w:
                f[f"w_{c}"] = w[c].astype(float)
        if "wind_direction_10m" in w:
            rad = np.deg2rad(w["wind_direction_10m"].astype(float))
            f["w_wind_u"] = -w["wind_speed_10m"] * np.sin(rad)
            f["w_wind_v"] = -w["wind_speed_10m"] * np.cos(rad)
            f = f.drop(columns=["w_wind_direction_10m"], errors="ignore")
        if "precipitation" in w:
            f["w_precip_24h"] = w["precipitation"].rolling(24, min_periods=1).sum()
        if "boundary_layer_height" in w:
            f["w_blh_rmean24"] = w["boundary_layer_height"].rolling(24, min_periods=12).mean()
        if "temperature_2m" in w:
            f["w_temp_diff24"] = w["temperature_2m"] - w["temperature_2m"].shift(24)
        if "relative_humidity_2m" in w:
            f["w_rh_rmean24"] = w["relative_humidity_2m"].rolling(24, min_periods=12).mean()

    f = f.join(_calendar(pd.Series(f.index, index=f.index), prefix="t_"))
    f["location_id"] = df["location_id"].ffill().bfill()
    return f


def add_targets(features: pd.DataFrame, hourly_target: pd.Series, imputed: pd.Series | None = None,
                horizons=HORIZONS) -> pd.DataFrame:
    """Append y_h = pm25(t+h). Interpolated target hours are set to NaN so models are never
    trained or scored on values that were not actually observed."""
    y = hourly_target.reindex(features.index).astype(float)
    if imputed is not None:
        y = y.mask(imputed.reindex(features.index).fillna(False).astype(bool))
    targets = {f"y_{h}": y.shift(-h) for h in horizons}
    return pd.concat([features, pd.DataFrame(targets, index=features.index)], axis=1)


TARGET_CAL_COLS = ["tgt_hour_sin", "tgt_hour_cos", "tgt_dow", "tgt_is_weekend", "tgt_is_festival"]


def design_matrix(feat: pd.DataFrame, h: int, feature_cols: list[str]) -> pd.DataFrame:
    """Features for horizon h = issue-time features + calendar of the target time (known ahead).

    ``feat`` must contain a UTC ``ts`` column (issue time)."""
    X = feat[feature_cols].copy()
    cal = _calendar(feat["ts"] + pd.Timedelta(hours=h), prefix="tgt_")
    for c in TARGET_CAL_COLS:
        X[c] = cal[c].values
    return X


def base_feature_columns(feat: pd.DataFrame) -> list[str]:
    drop = {"location_id"}
    return [c for c in feat.columns if not c.startswith("y_") and c not in drop and c != "ts"]
