"""Current conditions, history series and paginated records."""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from airsense.app.db.models import Measurement, Station
from airsense.app.services.data import UNITS, cached, get_station, measurements_long, nan_to_none, now_utc, resample
from airsense.ml.evaluation import aqi_category, pm25_sub_index


def latest_all(db: Session) -> list[dict]:
    def build():
        stations = db.execute(select(Station).order_by(Station.name)).scalars().all()
        last = dict(db.execute(select(Measurement.station_id, func.max(Measurement.ts)).group_by(Measurement.station_id)).all())
        out = []
        for s in stations:
            t = last.get(s.id)
            if t is None:
                out.append({"station": s, "observed_at": None, "pm25": None, "aqi": None, "category": None,
                            "readings": [], "pm25_24h_mean": None, "pm25_change_24h": None})
                continue
            df = measurements_long(db, [s.id], start=t - timedelta(hours=48), end=t)
            readings = []
            for p in UNITS:
                d = df[df.parameter == p].sort_values("ts")
                v = d.iloc[-1] if len(d) else None
                readings.append({"parameter": p, "value": float(v.value) if v is not None else None, "unit": UNITS[p],
                                 "ts": v.ts.to_pydatetime() if v is not None else None})
            pm = df[df.parameter == "pm25"].set_index("ts")["value"].sort_index()
            cur = float(pm.iloc[-1]) if len(pm) else None
            obs_at = pm.index[-1].to_pydatetime() if len(pm) else t
            last24 = pm[pm.index > pm.index[-1] - pd.Timedelta(hours=24)] if len(pm) else pm
            prev = pm[(pm.index <= pm.index[-1] - pd.Timedelta(hours=24))] if len(pm) else pm
            mean24 = float(last24.mean()) if len(last24) >= 12 else None
            out.append({"station": s, "observed_at": obs_at, "pm25": cur,
                        "aqi": pm25_sub_index(mean24 if mean24 is not None else cur) if cur is not None else None,
                        "category": aqi_category(mean24 if mean24 is not None else cur),
                        "readings": readings, "pm25_24h_mean": mean24,
                        "pm25_change_24h": (cur - float(prev.iloc[-1])) if cur is not None and len(prev) else None})
        return out
    return cached(db, ("latest_all",), build)


def city_summary(latest: list[dict]) -> dict:
    rep = [x for x in latest if x["pm25"] is not None]
    if not rep:
        return {"observed_at": None, "stations_reporting": 0, "stations_total": len(latest), "pm25_mean": None,
                "pm25_max": None, "worst_station": None, "aqi": None, "category": None, "data_lag_hours": None}
    newest = max(x["observed_at"] for x in rep)
    fresh = [x for x in rep if x["observed_at"] >= newest - timedelta(hours=6)]
    vals = [x["pm25_24h_mean"] if x["pm25_24h_mean"] is not None else x["pm25"] for x in fresh]
    worst = max(fresh, key=lambda x: x["pm25"])
    mean = float(np.mean(vals))
    return {"observed_at": newest, "stations_reporting": len(fresh), "stations_total": len(latest),
            "pm25_mean": round(mean, 1), "pm25_max": round(worst["pm25"], 1), "worst_station": worst["station"],
            "aqi": pm25_sub_index(mean), "category": aqi_category(mean),
            "data_lag_hours": round((now_utc() - newest).total_seconds() / 3600, 1)}


def series(db: Session, station_id: int, parameter: str, start: datetime | None, end: datetime | None,
           resolution: str) -> dict:
    st = get_station(db, station_id)
    if end is None:
        end = db.scalar(select(func.max(Measurement.ts)).where(Measurement.station_id == station_id))
    if start is None and end is not None:
        start = end - {"hour": timedelta(days=14), "day": timedelta(days=365), "month": timedelta(days=730)}[resolution]
    df = measurements_long(db, [station_id], [parameter], start, end)
    agg = resample(df[["ts", "value"]], resolution)
    return {"station_id": st.id, "station_name": st.name, "parameter": parameter, "unit": UNITS[parameter],
            "resolution": resolution,
            "points": [{"ts": r.ts.to_pydatetime(), "value": nan_to_none(r.value), "n": int(r.n)} for r in agg.itertuples()]}


def records(db: Session, station_id: int | None, parameter: str | None, start, end, page: int, page_size: int,
            sort: str = "desc") -> dict:
    q = select(Measurement, Station.name).join(Station, Station.id == Measurement.station_id)
    cq = select(func.count(Measurement.id))
    for cond in ([Measurement.station_id == station_id] if station_id else []) + \
                ([Measurement.parameter == parameter] if parameter else []) + \
                ([Measurement.ts >= start] if start else []) + ([Measurement.ts <= end] if end else []):
        q, cq = q.where(cond), cq.where(cond)
    total = db.scalar(cq) or 0
    order = Measurement.ts.desc() if sort == "desc" else Measurement.ts.asc()
    rows = db.execute(q.order_by(order, Measurement.id).offset((page - 1) * page_size).limit(page_size)).all()
    items = [{"ts": m.ts, "station_id": m.station_id, "station_name": name, "parameter": m.parameter,
              "value": round(m.value, 3), "unit": UNITS[m.parameter], "is_imputed": m.is_imputed,
              "is_outlier": m.is_outlier} for m, name in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "pages": max(1, -(-total // page_size))}
