"""Forecast orchestration: DB data -> ML model -> persisted forecast. Also model-registry sync and
evaluation views. Forecasts are cached per (station, model version, issue time)."""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

import pandas as pd
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from airsense.app.core.config import get_settings
from airsense.app.core.errors import NotFound, ServiceUnavailable, Unprocessable
from airsense.app.db.models import Forecast, ForecastPoint, ModelVersion, Station
from airsense.app.services.data import get_station, station_hourly, station_weather
from airsense.ml import predict
from airsense.ml.evaluation import ALERT_THRESHOLD, aqi_category

log = logging.getLogger(__name__)


def sync_model_registry(db: Session) -> ModelVersion | None:
    """Mirror models/registry.json into the model_versions table (idempotent)."""
    s = get_settings()
    try:
        reg = predict.registry(s.models_dir)
    except predict.ModelNotAvailable:
        return None
    active = None
    for v in reg["versions"]:
        mv = db.scalar(select(ModelVersion).where(ModelVersion.version == v["version"]))
        meta_path = s.models_dir / v["version"] / "metadata.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        if mv is None:
            mv = ModelVersion(version=v["version"], algorithm=meta.get("algorithm", "XGBoost"),
                              artifact_path=v["path"], data_hash=v["data_hash"],
                              trained_at=datetime.fromisoformat(v["created_at"]), metrics=meta)
            db.add(mv)
        else:
            mv.metrics = meta
        mv.is_active = v["version"] == reg["active"]
        if mv.is_active:
            active = mv
    db.commit()
    return active


def active_model(db: Session) -> ModelVersion:
    mv = db.scalar(select(ModelVersion).where(ModelVersion.is_active))
    if mv is None:
        mv = sync_model_registry(db)
    if mv is None:
        raise ServiceUnavailable("No trained model is available. Run the training pipeline.")
    return mv


def activate_version(db: Session, version: str) -> ModelVersion:
    s = get_settings()
    reg_path = s.models_dir / "registry.json"
    reg = json.loads(reg_path.read_text())
    if not any(v["version"] == version for v in reg["versions"]):
        raise NotFound(f"Model version {version} not found.")
    reg["active"] = version
    reg_path.write_text(json.dumps(reg, indent=2))
    db.execute(update(ModelVersion).values(is_active=False))
    db.commit()
    return sync_model_registry(db)


def get_forecast(db: Session, station_id: int, force: bool = False) -> Forecast:
    st = get_station(db, station_id)
    mv = active_model(db)
    hourly = station_hourly(db, station_id, hours=24 * 9)
    if hourly.empty or hourly["pm25"].notna().sum() < 24:
        raise Unprocessable(f"Not enough recent PM2.5 data at {st.name} to produce a forecast.")
    issued = hourly.loc[hourly["pm25"].notna(), "ts"].max().to_pydatetime()

    existing = db.scalar(select(Forecast).options(selectinload(Forecast.points)).where(
        Forecast.station_id == station_id, Forecast.model_version_id == mv.id, Forecast.issued_at == issued))
    if existing and not force:
        return existing
    if existing and force:
        db.delete(existing)
        db.flush()

    weather = station_weather(db, station_id, hourly.ts.min() - timedelta(hours=24), hourly.ts.max())
    try:
        res = predict.forecast_station(hourly, weather, version=mv.version, models_dir=get_settings().models_dir)
    except predict.InsufficientData as e:
        raise Unprocessable(str(e)) from e
    except predict.ModelNotAvailable as e:
        raise ServiceUnavailable(str(e)) from e
    fc = Forecast(station_id=station_id, model_version_id=mv.id, issued_at=issued, latest_pm25=res["latest_pm25"],
                  interval_scale=res["interval_scale"],
                  explanations={str(h): v for h, v in res["explanations"].items()})
    fc.points = [ForecastPoint(horizon=p.horizon, target_time=p.target_time.to_pydatetime(), pm25=p.pm25,
                               lower=p.lower, upper=p.upper, p_exceed=p.p_exceed, category=p.category)
                 for p in res["points"]]
    db.add(fc)
    db.commit()
    db.refresh(fc)
    log.info("forecast generated", extra={"path": f"station={station_id}"})
    return fc


def probability_for(fc: Forecast, point: ForecastPoint, threshold: float) -> float:
    if abs(threshold - ALERT_THRESHOLD) < 1e-9:
        return point.p_exceed
    return predict.exceed_probability(fc.model_version.version, point.horizon, point.pm25, fc.interval_scale,
                                      threshold, get_settings().models_dir)


def best_window(points: list[ForecastPoint], width: int = 2) -> dict | None:
    if len(points) < width:
        return None
    best = min(range(len(points) - width + 1), key=lambda i: sum(p.pm25 for p in points[i:i + width]))
    sl = points[best:best + width]
    return {"start": sl[0].target_time, "end": sl[-1].target_time + timedelta(hours=1),
            "mean_pm25": round(sum(p.pm25 for p in sl) / width, 1), "category": aqi_category(sl[0].pm25)}


def forecast_payload(fc: Forecast, threshold: float) -> dict:
    pts = sorted(fc.points, key=lambda p: p.horizon)
    out_pts = []
    for p in pts:
        out_pts.append({"horizon": p.horizon, "target_time": p.target_time, "pm25": p.pm25, "lower": p.lower,
                        "upper": p.upper, "p_exceed": probability_for(fc, p, threshold), "category": p.category})
    peak = max(out_pts, key=lambda p: p["pm25"])
    return {"station": fc.station, "model_version": fc.model_version.version, "issued_at": fc.issued_at,
            "generated_at": fc.generated_at, "latest_pm25": fc.latest_pm25, "threshold": threshold,
            "interval_level": 0.8, "points": out_pts, "explanations": fc.explanations or {},
            "peak": peak, "hours_above_threshold": sum(1 for p in out_pts if p["pm25"] > threshold),
            "best_window": best_window(pts)}


# ---------------------------------------------------------------- evaluation views
def model_metrics(db: Session, version: str) -> dict:
    s = get_settings()
    path = s.models_dir / version / "metrics.json"
    if not path.exists():
        raise NotFound(f"Metrics for {version} not found.")
    m = pd.DataFrame(json.loads(path.read_text()))
    test = m[m.split == "test"]
    persist = test[test.model == "Persistence"].set_index("horizon")["mae"]
    rows = []
    for r in test.itertuples():
        rows.append({"model": r.model, "horizon": int(r.horizon), "mae": r.mae, "rmse": r.rmse, "r2": r.r2,
                     "bias": r.bias, "n": int(r.n),
                     "skill_vs_persistence": (1 - r.mae / persist.get(r.horizon)) if persist.get(r.horizon) else None,
                     "interval_coverage_80": getattr(r, "interval_coverage_80", None)
                     if pd.notna(getattr(r, "interval_coverage_80", None)) else None,
                     "alert": r.alert if isinstance(getattr(r, "alert", None), dict) else None})
    meta = json.loads((s.models_dir / version / "metadata.json").read_text())
    sarima_path = s.models_dir.parent / "reports" / "model_results" / "sarima_daily.json"
    sarima = json.loads(sarima_path.read_text()) if sarima_path.exists() else None
    return {"version": version, "test_window_start": meta["split"]["test_start"], "metrics": rows,
            "target_modes": meta.get("target_modes"), "importance": meta.get("global_importance_h24"),
            "sarima_daily": sarima}


def evaluation_series(db: Session, version: str, horizon: int, station_id: int | None, days: int = 30) -> dict:
    s = get_settings()
    path = s.models_dir / version / f"test_predictions_h{horizon}.parquet"
    if not path.exists():
        raise NotFound(f"No stored test predictions for horizon {horizon} (available: 1, 3, 6, 12, 24).")
    p = pd.read_parquet(path)
    p["ts"] = pd.to_datetime(p["ts"], utc=True) + pd.Timedelta(hours=horizon)  # x-axis = target time
    ext_ids = {int(x) for x in p.location_id.unique()}
    model_stations = db.execute(select(Station).where(Station.used_in_model).order_by(Station.name)).scalars().all()
    available = [st for st in model_stations if int(st.external_id) in ext_ids]
    if station_id is None:
        if not available:
            raise NotFound("No model stations available.")
        st = available[0]
    else:
        st = get_station(db, station_id)
    q = p[p.location_id == int(st.external_id)].sort_values("ts")
    if q.empty:
        raise NotFound(f"{st.name} is not part of the model's test set (coverage below threshold).")
    q = q[q.ts >= q.ts.max() - pd.Timedelta(days=days)]
    resid = (q.xgb - q.y).dropna()
    hist_counts = pd.cut(resid, 30).value_counts(sort=False) if len(resid) else pd.Series(dtype=int)
    return {"version": version, "horizon": horizon, "station_id": st.id, "station_name": st.name,
            "available_station_ids": [a.id for a in available],
            "mae_window": float(resid.abs().mean()) if len(resid) else None,
            "points": [{"ts": r.ts.to_pydatetime(), "actual": None if pd.isna(r.y) else float(r.y),
                        "xgboost": float(r.xgb), "lower": float(r.lo), "upper": float(r.hi),
                        "persistence": float(r.persistence), "linear": float(r.lr)} for r in q.itertuples()],
            "residual_histogram": [{"bin": float(iv.mid), "count": int(c)} for iv, c in hist_counts.items()]}


def utcnow() -> datetime:
    return datetime.now(UTC)
