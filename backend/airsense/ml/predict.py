"""Inference: load a versioned model bundle and produce a 24-hour PM2.5 forecast with
uncertainty intervals, threshold-exceedance probabilities and per-forecast explanations.

Used by the FastAPI forecasting service - the API never returns hard-coded predictions.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

from airsense.ml.evaluation import ALERT_THRESHOLD, aqi_category
from airsense.ml.feature_engineering import build_features, design_matrix
from airsense.ml.paths import MODELS_DIR

_lock = threading.Lock()
_cache: dict[str, dict] = {}

# Human-readable feature names for explanations shown in the UI
FEATURE_LABELS = {
    "pm25_lag0": "Current PM2.5", "pm25_lag1": "PM2.5 1 h ago", "pm25_lag2": "PM2.5 2 h ago", "pm25_lag3": "PM2.5 3 h ago",
    "pm25_lag6": "PM2.5 6 h ago", "pm25_lag12": "PM2.5 12 h ago", "pm25_lag24": "PM2.5 same hour yesterday",
    "pm25_lag48": "PM2.5 two days ago", "pm25_lag168": "PM2.5 one week ago", "pm25_rmean12": "12 h average PM2.5",
    "pm25_rstd3": "3 h PM2.5 variability", "pm25_rstd6": "6 h PM2.5 variability", "pm25_rstd12": "12 h PM2.5 variability",
    "pm25_missing_24h": "Missing hours (24 h)", "w_rh_rmean24": "24 h mean humidity", "w_temp_diff24": "24 h temperature change",
    "w_precipitation": "Rain (this hour)", "tgt_dow": "Target weekday", "tgt_is_weekend": "Weekend", "t_dow": "Weekday",
    "no2_rmean24": "24 h average NO2", "co_rmean24": "24 h average CO", "o3_rmean24": "24 h average O3",
    "so2_rmean24": "24 h average SO2", "t_season_winter": "Winter season", "t_season_monsoon": "Monsoon season",
    "t_season_post_monsoon": "Post-monsoon season", "t_season_summer": "Summer season",
    "pm25_rmean3": "3 h average PM2.5", "pm25_rmean6": "6 h average PM2.5", "pm25_rmean24": "24 h average PM2.5",
    "pm25_rmean168": "7-day average PM2.5", "pm25_rstd24": "24 h PM2.5 variability", "pm25_diff1": "1 h PM2.5 trend",
    "pm25_diff24": "24 h PM2.5 trend", "w_boundary_layer_height": "Mixing height (boundary layer)",
    "w_blh_rmean24": "24 h mean mixing height", "w_wind_speed_10m": "Wind speed", "w_wind_u": "East-west wind",
    "w_wind_v": "North-south wind", "w_relative_humidity_2m": "Humidity", "w_temperature_2m": "Temperature",
    "w_precip_24h": "Rain (last 24 h)", "w_surface_pressure": "Surface pressure", "tgt_hour_sin": "Target hour of day",
    "tgt_hour_cos": "Target hour of day", "t_hour_sin": "Current hour", "t_hour_cos": "Current hour",
    "t_month_sin": "Season (month)", "t_month_cos": "Season (month)", "tgt_is_festival": "Festival period (Diwali)",
    "t_is_festival": "Festival period (Diwali)", "pm10_lag0": "Current PM10", "pm10_rmean24": "24 h average PM10",
    "no2_lag0": "Current NO2", "co_lag0": "Current CO", "o3_lag0": "Current O3", "so2_lag0": "Current SO2",
    "pm_ratio_rmean24": "PM2.5/PM10 ratio", "pm25_rmax24": "24 h peak PM2.5", "pm25_rmin24": "24 h minimum PM2.5",
}


class ModelNotAvailable(RuntimeError):
    pass


class InsufficientData(RuntimeError):
    pass


def registry(models_dir: Path = MODELS_DIR) -> dict:
    p = models_dir / "registry.json"
    if not p.exists():
        raise ModelNotAvailable(f"No model registry at {p}. Run `python -m airsense.ml.train`.")
    return json.loads(p.read_text())


def load_bundle(version: str | None = None, models_dir: Path = MODELS_DIR) -> dict:
    reg = registry(models_dir)
    version = version or reg["active"]
    with _lock:
        if version not in _cache:
            entry = next((v for v in reg["versions"] if v["version"] == version), None)
            if entry is None:
                raise ModelNotAvailable(f"Unknown model version {version}")
            _cache[version] = joblib.load(models_dir / entry["path"])
        return _cache[version]


@dataclass
class ForecastPoint:
    horizon: int
    target_time: pd.Timestamp
    pm25: float
    lower: float
    upper: float
    p_exceed: float
    category: str | None


def exceed_probability(version: str | None, horizon: int, yhat: float, scale: float, threshold: float,
                       models_dir: Path = MODELS_DIR) -> float:
    """Public helper: P(PM2.5 > threshold) for a stored forecast point and any user threshold."""
    b = load_bundle(version, models_dir)
    return round(_exceed_prob(yhat, scale, b["conformal"][horizon]["quantiles"], threshold), 3)


def _exceed_prob(yhat: float, scale: float, quantiles: list[float], threshold: float) -> float:
    """P(Y > threshold) from the empirical (validation) distribution of normalised residuals."""
    q = np.asarray(quantiles)
    return float(np.mean(yhat + q * scale > threshold))


def forecast_station(hourly: pd.DataFrame, weather: pd.DataFrame | None, *, version: str | None = None,
                     horizons: list[int] | None = None, threshold: float = ALERT_THRESHOLD,
                     explain: bool = True, models_dir: Path = MODELS_DIR) -> dict:
    """Forecast from the latest hour present in ``hourly`` (one station, UTC ``ts`` column)."""
    b = load_bundle(version, models_dir)
    if hourly.empty or hourly["pm25"].notna().sum() < 24:
        raise InsufficientData("Need at least 24 hourly PM2.5 observations to forecast.")
    feats = build_features(hourly, weather)
    last_obs = hourly.loc[hourly["pm25"].notna(), "ts"].max()
    issue = feats.loc[[last_obs]].reset_index()
    if pd.isna(issue["pm25_lag0"].iloc[0]):
        raise InsufficientData("Latest PM2.5 observation missing.")
    for c in b["feature_columns"]:
        if c not in issue:
            issue[c] = np.nan  # e.g. a station without SO2 sensor -> XGBoost handles NaN natively
    persist = float(issue["pm25_lag0"].iloc[0])
    scale = float((issue["pm25_rstd24"].fillna(10.0) + 5.0).iloc[0])

    points, explanations = [], {}
    for h in horizons or b["horizons"]:
        X = design_matrix(issue, h, b["feature_columns"])[b["design_columns"]]
        model = b["xgb"][h]
        mode = b.get("target_modes", {}).get(h, "level")
        base = persist if mode == "delta" else 0.0
        yhat = max(0.0, base + float(model.predict(X)[0]))
        c = b["conformal"][h]
        lo, hi = max(0.0, yhat + c["lo"] * scale), yhat + c["hi"] * scale
        points.append(ForecastPoint(h, last_obs + pd.Timedelta(hours=h), round(yhat, 2), round(lo, 2), round(hi, 2),
                                    round(_exceed_prob(yhat, scale, c["quantiles"], threshold), 3),
                                    aqi_category(yhat)))
        if explain and h in (1, 6, 12, 24):
            contrib = model.get_booster().predict(xgb.DMatrix(X), pred_contribs=True)[0]
            s = pd.Series(contrib[:-1], index=X.columns)
            top = s.reindex(s.abs().sort_values(ascending=False).index).head(6)
            explanations[h] = [{"feature": k, "label": FEATURE_LABELS.get(k, k.replace("_", " ")),
                                "value": None if pd.isna(X[k].iloc[0]) else round(float(X[k].iloc[0]), 3),
                                "contribution": round(float(v), 2)} for k, v in top.items()]
            explanations[h].append({"feature": "_base", "label": "Baseline" + (" (current level)" if mode == "delta" else ""),
                                    "value": None, "contribution": round(float(contrib[-1] + base), 2)})
    return {
        "model_version": b["version"],
        "issued_at": last_obs,
        "latest_pm25": persist,
        "interval_scale": scale,
        "threshold": threshold,
        "interval_level": 1 - b["interval_alpha"],
        "points": points,
        "explanations": explanations,
    }
