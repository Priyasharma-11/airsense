"""AirSense FastAPI application factory."""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import select, text

from airsense.app.api import alerts, auth, data, ml, users
from airsense.app.core.config import get_settings
from airsense.app.core.errors import register_exception_handlers
from airsense.app.core.logging import RequestContextMiddleware, configure_logging
from airsense.app.core.ratelimit import limiter
from airsense.app.db.models import ModelVersion
from airsense.app.db.session import SessionLocal, get_engine

log = logging.getLogger("airsense")
API_DESCRIPTION = """
**AirSense** - air-quality monitoring, analysis and PM2.5 forecasting for Pune, India.

* Data: OpenAQ station measurements (CPCB/MPCB/IITM), ERA5 weather (Open-Meteo); CAMS used only as a benchmark.
* Model: direct multi-horizon XGBoost (1-24 h) with split-conformal 80 % intervals.
* Auth: JWT bearer token (use **Authorize** with your email/password) or the httpOnly session cookie.
"""


def _scheduler(stop: threading.Event, hours: int):
    from airsense.app.services import ingestion

    while not stop.wait(hours * 3600):
        db = SessionLocal()
        try:
            ingestion.incremental_sync(db, days=3)
        except Exception:
            log.exception("scheduled ingestion failed")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    get_engine()
    db = SessionLocal()
    try:
        from airsense.app.services.forecasting import sync_model_registry

        mv = sync_model_registry(db)
        if mv:
            from airsense.ml.predict import load_bundle

            load_bundle(mv.version, s.models_dir)  # warm the model cache
            log.info("model %s loaded", mv.version)
    except Exception:
        log.exception("model registry sync failed at startup")
    finally:
        db.close()
    if s.env != "test":
        from airsense.app.services.data import warm_cache

        def _warm():
            try:
                warm_cache()
                log.info("analytics cache warmed")
            except Exception:
                log.exception("cache warm-up failed")

        threading.Thread(target=_warm, daemon=True, name="cache-warmup").start()
    stop = threading.Event()
    if s.enable_scheduler:
        threading.Thread(target=_scheduler, args=(stop, s.ingestion_interval_hours), daemon=True).start()
    yield
    stop.set()


def create_app() -> FastAPI:
    s = get_settings()
    configure_logging(s.log_level, json_logs=s.env == "production")
    app = FastAPI(title=s.app_name, version="1.0.0", description=API_DESCRIPTION, lifespan=lifespan,
                  docs_url="/docs", redoc_url="/redoc", openapi_url="/openapi.json")
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    register_exception_handlers(app)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                       allow_headers=["Authorization", "Content-Type", "X-Request-ID"])
    app.add_middleware(RequestContextMiddleware)

    api = APIRouter(prefix=s.api_prefix)
    for r in (auth.router, users.router, data.stations_router, data.aq_router, data.weather_router,
              data.analytics_router, data.geo_router, ml.forecast_router, ml.models_router, alerts.router,
              alerts.ingest_router, data.meta_router):
        api.include_router(r)
    app.include_router(api)

    @app.get("/health", tags=["Health"], summary="Liveness probe")
    def health():
        return {"status": "ok"}

    @app.get("/health/ready", tags=["Health"], summary="Readiness probe: database + model")
    def ready():
        checks = {}
        try:
            with get_engine().connect() as c:
                c.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:  # pragma: no cover
            checks["database"] = f"error: {e.__class__.__name__}"
        db = SessionLocal()
        try:
            mv = db.scalar(select(ModelVersion).where(ModelVersion.is_active))
            checks["model"] = mv.version if mv else "missing"
        except Exception as e:  # pragma: no cover
            checks["model"] = f"error: {e.__class__.__name__}"
        finally:
            db.close()
        ok = checks["database"] == "ok" and checks["model"] not in ("missing",) and not checks["model"].startswith("error")
        from fastapi.responses import JSONResponse

        return JSONResponse({"status": "ready" if ok else "degraded", "checks": checks}, status_code=200 if ok else 503)

    return app


app = create_app()
