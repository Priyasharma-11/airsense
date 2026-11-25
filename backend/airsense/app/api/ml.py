"""Forecasting and model-evaluation endpoints (backed by the trained, versioned model)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from airsense.app.core.config import get_settings
from airsense.app.core.errors import AppError, Unprocessable
from airsense.app.core.ratelimit import limiter
from airsense.app.db.models import ModelVersion, Station
from airsense.app.deps import DB, AdminUser, OptionalUser
from airsense.app.schemas import ForecastOut, ModelVersionOut
from airsense.app.services import forecasting

forecast_router = APIRouter(prefix="/forecasts", tags=["Forecasting"])
models_router = APIRouter(prefix="/models", tags=["Model evaluation"])
_s = get_settings()
EVAL_HORIZONS = [1, 3, 6, 12, 24]


@forecast_router.get("/{station_id}", response_model=ForecastOut)
@limiter.limit("30/minute")
def forecast(request: Request, station_id: int, db: DB, user: OptionalUser,
             horizon: Annotated[int, Query(ge=1, le=24)] = 24,
             threshold: Annotated[float | None, Query(gt=0, le=500)] = None, refresh: bool = False):
    """24-hour PM2.5 forecast issued from the latest available observation at the station."""
    if threshold is None:
        threshold = user.preferences.pm25_threshold if user and user.preferences else 60.0
    fc = forecasting.get_forecast(db, station_id, force=refresh)
    out = forecasting.forecast_payload(fc, threshold)
    out["points"] = [p for p in out["points"] if p["horizon"] <= horizon]
    out["peak"] = max(out["points"], key=lambda p: p["pm25"])
    out["hours_above_threshold"] = sum(1 for p in out["points"] if p["pm25"] > threshold)
    return out


@forecast_router.get("", summary="Next-24 h outlook for every station")
@limiter.limit("20/minute")
def forecast_overview(request: Request, db: DB):
    out, errors = [], []
    for st in db.execute(select(Station).where(Station.is_active).order_by(Station.name)).scalars():
        try:
            fc = forecasting.get_forecast(db, st.id)
        except AppError as e:
            errors.append({"station_id": st.id, "name": st.name, "error": e.message})
            continue
        pts = sorted(fc.points, key=lambda p: p.horizon)
        peak = max(pts, key=lambda p: p.pm25)
        out.append({"station_id": st.id, "name": st.name, "issued_at": fc.issued_at, "latest_pm25": fc.latest_pm25,
                    "peak_pm25": peak.pm25, "peak_time": peak.target_time, "peak_category": peak.category,
                    "max_p_exceed": max(p.p_exceed for p in pts),
                    "sparkline": [round(p.pm25, 1) for p in pts]})
    return {"stations": out, "unavailable": errors}


@models_router.get("", response_model=list[ModelVersionOut])
def list_models(db: DB):
    forecasting.sync_model_registry(db)
    return db.execute(select(ModelVersion).order_by(ModelVersion.trained_at.desc())).scalars().all()


@models_router.get("/active", response_model=ModelVersionOut)
def active(db: DB):
    return forecasting.active_model(db)


@models_router.get("/{version}/metrics")
def metrics(version: str, db: DB):
    return forecasting.model_metrics(db, version)


@models_router.get("/{version}/evaluation")
def evaluation(version: str, db: DB, horizon: Annotated[int, Query(description="One of 1, 3, 6, 12, 24")] = 24,
               station_id: int | None = None, days: Annotated[int, Query(ge=3, le=120)] = 30):
    if horizon not in EVAL_HORIZONS:
        raise Unprocessable(f"horizon must be one of {EVAL_HORIZONS}.")
    return forecasting.evaluation_series(db, version, horizon, station_id, days)


@models_router.post("/{version}/activate", response_model=ModelVersionOut)
def activate(version: str, db: DB, _: AdminUser):
    return forecasting.activate_version(db, version)
