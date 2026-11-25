"""Read-only data endpoints: stations, air quality, weather, analytics, geospatial."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select

from airsense.app.core.errors import Unprocessable
from airsense.app.db.models import Station, WeatherObservation
from airsense.app.deps import DB
from airsense.app.schemas import (
    CurrentOut,
    MeasurementRecord,
    Page,
    Pollutant,
    Resolution,
    Series,
    StationLatest,
    StationOut,
    WeatherOut,
)
from airsense.app.services import analytics, geo, measurements
from airsense.app.services.data import get_station
from airsense.ml.evaluation import ALERT_THRESHOLD, AQI_BANDS

stations_router = APIRouter(prefix="/stations", tags=["Monitoring stations"])
aq_router = APIRouter(prefix="/air-quality", tags=["Air quality"])
weather_router = APIRouter(prefix="/weather", tags=["Weather"])
analytics_router = APIRouter(prefix="/analytics", tags=["Analytics"])
geo_router = APIRouter(prefix="/geo", tags=["Geospatial"])
meta_router = APIRouter(prefix="/meta", tags=["Metadata"])

StationIds = Annotated[list[int] | None, Query(description="Filter by station ids (repeat the parameter)")]
Start = Annotated[datetime | None, Query(description="ISO-8601 start (UTC if no offset)")]
End = Annotated[datetime | None, Query(description="ISO-8601 end (UTC if no offset)")]


def _check_range(start, end):
    if start and end and start > end:
        raise Unprocessable("start must be before end.")


# ------------------------------------------------------------------ stations
@stations_router.get("", response_model=list[StationOut])
def list_stations(db: DB, q: Annotated[str | None, Query(max_length=100)] = None,
                  city: Annotated[str | None, Query(max_length=100)] = None,
                  provider: Annotated[str | None, Query(max_length=20)] = None):
    stmt = select(Station).order_by(Station.name)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Station.name.ilike(like), Station.city.ilike(like)))
    if city:
        stmt = stmt.where(Station.city == city)
    if provider:
        stmt = stmt.where(Station.provider == provider)
    return db.execute(stmt).scalars().all()


@stations_router.get("/nearest", response_model=list[dict])
def nearest(db: DB, lat: Annotated[float, Query(ge=-90, le=90)], lon: Annotated[float, Query(ge=-180, le=180)],
            limit: Annotated[int, Query(ge=1, le=10)] = 3):
    return [{"station": StationOut.model_validate(r["station"]).model_dump(), "distance_km": r["distance_km"]}
            for r in geo.nearest_stations(db, lat, lon, limit)]


@stations_router.get("/{station_id}", response_model=StationOut)
def station_detail(station_id: int, db: DB):
    return get_station(db, station_id)


@stations_router.get("/{station_id}/latest", response_model=StationLatest)
def station_latest(station_id: int, db: DB):
    get_station(db, station_id)
    return next(x for x in measurements.latest_all(db) if x["station"].id == station_id)


# ------------------------------------------------------------------ air quality
@aq_router.get("/current", response_model=CurrentOut)
def current(db: DB):
    latest = measurements.latest_all(db)
    return {"summary": measurements.city_summary(latest), "stations": latest}


@aq_router.get("/history", response_model=Series)
def history(db: DB, station_id: int, parameter: Pollutant = "pm25", start: Start = None, end: End = None,
            resolution: Resolution = "hour"):
    _check_range(start, end)
    if resolution == "hour" and start and end and end - start > timedelta(days=120):
        raise Unprocessable("Hourly resolution is limited to 120 days; use resolution=day or month.")
    return measurements.series(db, station_id, parameter, start, end, resolution)


@aq_router.get("/compare", response_model=list[Series])
def compare(db: DB, station_ids: Annotated[list[int], Query(min_length=1, max_length=10)],
            parameter: Pollutant = "pm25", start: Start = None, end: End = None, resolution: Resolution = "day"):
    _check_range(start, end)
    return [measurements.series(db, sid, parameter, start, end, resolution) for sid in station_ids]


@aq_router.get("/records", response_model=Page[MeasurementRecord])
def records(db: DB, station_id: int | None = None, parameter: Pollutant | None = None, start: Start = None,
            end: End = None, page: Annotated[int, Query(ge=1)] = 1,
            page_size: Annotated[int, Query(ge=1, le=500)] = 50, sort: Literal["asc", "desc"] = "desc"):
    _check_range(start, end)
    return measurements.records(db, station_id, parameter, start, end, page, page_size, sort)


# ------------------------------------------------------------------ weather
@weather_router.get("/current", response_model=WeatherOut)
def weather_current(db: DB, station_id: int):
    get_station(db, station_id)
    last_meas = measurements.latest_all(db)
    obs = next((x["observed_at"] for x in last_meas if x["station"].id == station_id), None)
    q = select(WeatherObservation).where(WeatherObservation.station_id == station_id)
    if obs:
        q = q.where(WeatherObservation.ts <= obs)
    w = db.scalar(q.order_by(WeatherObservation.ts.desc()).limit(1))
    if w is None:
        raise Unprocessable("No weather data for this station.")
    return w


@weather_router.get("/history", response_model=list[WeatherOut])
def weather_history(db: DB, station_id: int, start: Start = None, end: End = None):
    get_station(db, station_id)
    end = end or db.scalar(select(func.max(WeatherObservation.ts)).where(WeatherObservation.station_id == station_id))
    start = start or (end - timedelta(days=7) if end else None)
    _check_range(start, end)
    if start and end and end - start > timedelta(days=60):
        raise Unprocessable("Weather history is limited to 60 days per request.")
    return db.execute(select(WeatherObservation).where(WeatherObservation.station_id == station_id,
                                                       WeatherObservation.ts >= start, WeatherObservation.ts <= end)
                      .order_by(WeatherObservation.ts)).scalars().all()


# ------------------------------------------------------------------ analytics
@analytics_router.get("/summary")
def a_summary(db: DB):
    return analytics.summary(db)


@analytics_router.get("/insights")
def a_insights(db: DB):
    return analytics.insights(db)


@analytics_router.get("/diurnal")
def a_diurnal(db: DB, parameter: Pollutant = "pm25", station_ids: StationIds = None, start: Start = None, end: End = None):
    _check_range(start, end)
    return analytics.diurnal(db, parameter, station_ids, start, end)


@analytics_router.get("/monthly")
def a_monthly(db: DB, parameter: Pollutant = "pm25", station_ids: StationIds = None, start: Start = None, end: End = None):
    _check_range(start, end)
    return analytics.monthly(db, parameter, station_ids, start, end)


@analytics_router.get("/heatmap")
def a_heatmap(db: DB, parameter: Pollutant = "pm25", station_ids: StationIds = None, start: Start = None, end: End = None):
    _check_range(start, end)
    return analytics.heatmap(db, parameter, station_ids, start, end)


@analytics_router.get("/correlation")
def a_corr(db: DB, station_ids: StationIds = None, start: Start = None, end: End = None,
           method: Literal["pearson", "spearman"] = "spearman"):
    _check_range(start, end)
    return analytics.correlation(db, station_ids, start, end, method)


@analytics_router.get("/distribution")
def a_dist(db: DB, parameter: Pollutant = "pm25", station_ids: StationIds = None, start: Start = None, end: End = None,
           by: Literal["station", "month"] = "station"):
    _check_range(start, end)
    return analytics.distribution(db, parameter, station_ids, start, end, by)


@analytics_router.get("/station-comparison")
def a_compare(db: DB, parameter: Pollutant = "pm25", start: Start = None, end: End = None):
    _check_range(start, end)
    return analytics.station_comparison(db, parameter, start, end)


@analytics_router.get("/weather-relationship")
def a_weather(db: DB, variable: Literal["temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m",
                                        "boundary_layer_height", "surface_pressure"] = "wind_speed_10m",
              station_ids: StationIds = None, start: Start = None, end: End = None,
              sample: Annotated[int, Query(ge=100, le=5000)] = 2000):
    _check_range(start, end)
    return analytics.weather_relationship(db, variable, station_ids, start, end, sample)


# ------------------------------------------------------------------ geo
@geo_router.get("/stations", summary="GeoJSON FeatureCollection of stations with latest PM2.5")
def geo_stations(db: DB):
    return geo.station_geojson(db, measurements.latest_all(db))


@geo_router.get("/hotspots")
def geo_hotspots(db: DB, start: Start = None, end: End = None):
    _check_range(start, end)
    return geo.hotspots(db, start, end)


# ------------------------------------------------------------------ meta
@meta_router.get("/aqi-scale")
def aqi_scale():
    return {"pollutant": "pm25", "unit": "µg/m³", "standard": "CPCB National AQI (24-h average)",
            "alert_threshold": ALERT_THRESHOLD,
            "bands": [{"name": n, "min": lo, "max": hi if hi < 10_000 else None, "aqi_min": il, "aqi_max": ih,
                       "color": c} for n, lo, hi, il, ih, c in AQI_BANDS]}


@meta_router.get("/sources")
def sources(db: DB):
    from airsense.app.db.models import DataSource, IngestionRun

    srcs = db.execute(select(DataSource)).scalars().all()
    last = db.scalar(select(IngestionRun).where(IngestionRun.status == "success").order_by(IngestionRun.id.desc()))
    return {"sources": [{"slug": s.slug, "name": s.name, "url": s.url, "license": s.license, "kind": s.kind,
                         "description": s.description} for s in srcs],
            "last_ingestion": {"kind": last.kind, "finished_at": last.finished_at, "rows": last.rows_upserted}
            if last else None}
