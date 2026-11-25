"""Geospatial intelligence: GeoJSON station layer, statistically-defined hotspots, nearest stations.

Hotspots are defined by statistics, not by interpolated colour blobs: with ~10 monitors, spatial
interpolation (IDW / kriging) would be visually persuasive but statistically unjustified.
"""
from __future__ import annotations

import math

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from airsense.app.db.models import Station
from airsense.app.services import analytics
from airsense.app.services.data import nan_to_none
from airsense.ml.evaluation import AQI_BANDS, aqi_category

CATEGORY_COLORS = {name: color for name, *_, color in AQI_BANDS}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_stations(db: Session, lat: float, lon: float, limit: int = 3) -> list[dict]:
    if db.get_bind().dialect.name == "postgresql":
        rows = db.execute(text(
            "SELECT id, ST_Distance(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) / 1000.0 AS km "
            "FROM stations WHERE is_active ORDER BY geom <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography "
            "LIMIT :limit"), {"lat": lat, "lon": lon, "limit": limit}).all()
        ids = {r.id: float(r.km) for r in rows}
        stations = {s.id: s for s in db.execute(select(Station).where(Station.id.in_(ids))).scalars()}
        return [{"station": stations[i], "distance_km": round(k, 2)} for i, k in ids.items()]
    stations = db.execute(select(Station).where(Station.is_active)).scalars().all()
    ranked = sorted(((haversine_km(lat, lon, s.latitude, s.longitude), s) for s in stations), key=lambda x: x[0])
    return [{"station": s, "distance_km": round(d, 2)} for d, s in ranked[:limit]]


def hotspots(db: Session, start=None, end=None) -> dict:
    comp = analytics.station_comparison(db, "pm25", start, end)["stations"]
    stations = {s.id: s for s in db.execute(select(Station)).scalars()}
    comp = [c for c in comp if c["mean"] is not None and c["valid_days"] > 0]
    if not comp:
        return {"city_mean": None, "stations": [], "method": ""}
    means = np.array([c["mean"] for c in comp])
    exc = np.array([c["days_above_threshold"] / c["valid_days"] * 100 for c in comp])

    def z(x):
        sd = x.std()
        return (x - x.mean()) / sd if sd > 0 else np.zeros_like(x)

    score = 0.5 * z(means) + 0.5 * z(exc)
    out = []
    for c, sc, e in zip(comp, score, exc):
        s = stations[c["station_id"]]
        level = "hotspot" if sc > 0.75 else ("elevated" if sc > 0 else "typical")
        out.append({"station_id": s.id, "name": s.name, "latitude": s.latitude, "longitude": s.longitude,
                    "mean_pm25": round(c["mean"], 1), "p95_pm25": nan_to_none(c["p95"]),
                    "pct_days_above_threshold": round(float(e), 1), "days_above_threshold": c["days_above_threshold"],
                    "valid_days": c["valid_days"], "score": round(float(sc), 3), "level": level,
                    "category": aqi_category(c["mean"])})
    out.sort(key=lambda r: -r["score"])
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return {"city_mean": round(float(means.mean()), 1), "threshold": comp and 60.0, "stations": out,
            "method": "score = 0.5·z(mean PM2.5) + 0.5·z(% valid days with daily mean > 60 µg/m³); "
                      "hotspot if score > 0.75, elevated if > 0."}


def station_geojson(db: Session, latest: list[dict]) -> dict:
    feats = []
    for item in latest:
        s = item["station"]
        cat = item["category"]
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [s.longitude, s.latitude]},
                      "properties": {"id": s.id, "name": s.name, "city": s.city, "provider": s.provider,
                                     "pm25": item["pm25"], "aqi": item["aqi"], "category": cat,
                                     "color": CATEGORY_COLORS.get(cat, "#94a3b8"),
                                     "observed_at": item["observed_at"].isoformat() if item["observed_at"] else None,
                                     "used_in_model": s.used_in_model}})
    return {"type": "FeatureCollection", "features": feats}
