"""Exploratory analytics served to the dashboard. All computed from the database."""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from airsense.app.db.models import Station
from airsense.app.services.data import IST, UNITS, cached, nan_to_none, weather_all, wide_all
from airsense.ml.evaluation import ALERT_THRESHOLD, aqi_category, pm25_sub_index
from airsense.ml.feature_engineering import SEASON_OF_MONTH

POLLUTANT_LABELS = {"pm25": "PM2.5", "pm10": "PM10", "no2": "NO₂", "so2": "SO₂", "co": "CO", "o3": "O₃"}
WEATHER_LABELS = {"temperature_2m": "Temperature", "relative_humidity_2m": "Humidity", "precipitation": "Rainfall",
                  "wind_speed_10m": "Wind speed", "boundary_layer_height": "Mixing height",
                  "surface_pressure": "Pressure"}


def _utc(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _filtered(db: Session, station_ids: list[int] | None, start: datetime | None, end: datetime | None) -> pd.DataFrame:
    w = wide_all(db)
    if station_ids:
        w = w[w.station_id.isin(station_ids)]
    if start is not None:
        w = w[w.ts >= _utc(start)]
    if end is not None:
        w = w[w.ts <= _utc(end)]
    w = w.copy()
    loc = w.ts.dt.tz_convert(IST)
    w["hour"], w["dow"], w["month"] = loc.dt.hour, loc.dt.day_of_week, loc.dt.month
    w["ym"] = loc.dt.strftime("%Y-%m")
    w["date"] = loc.dt.date
    return w


def station_names(db: Session) -> dict[int, str]:
    return {s.id: s.name for s in db.execute(select(Station)).scalars()}


def diurnal(db: Session, parameter: str, station_ids=None, start=None, end=None) -> dict:
    w = _filtered(db, station_ids, start, end)
    names = station_names(db)
    city = w.groupby("hour")[parameter].mean()
    per = w.groupby(["station_id", "hour"])[parameter].mean().unstack(0)
    return {"parameter": parameter, "unit": UNITS[parameter], "hours": list(range(24)),
            "city": [nan_to_none(city.get(h)) for h in range(24)],
            "stations": [{"station_id": int(s), "name": names.get(int(s)), "values": [nan_to_none(per[s].get(h))
                          for h in range(24)]} for s in per.columns]}


def monthly(db: Session, parameter: str, station_ids=None, start=None, end=None) -> dict:
    w = _filtered(db, station_ids, start, end)
    g = w.groupby("ym")[parameter]
    m = pd.DataFrame({"mean": g.mean(), "p90": g.quantile(0.9), "n": g.count()})
    by_month = w.groupby("month")[parameter].mean()
    season = w.assign(season=w.month.map(SEASON_OF_MONTH)).groupby("season")[parameter].mean()
    return {"parameter": parameter, "unit": UNITS[parameter],
            "series": [{"month": k, "mean": nan_to_none(r["mean"]), "p90": nan_to_none(r["p90"]), "n": int(r["n"])}
                       for k, r in m.iterrows()],
            "calendar_month_mean": {int(k): nan_to_none(v) for k, v in by_month.items()},
            "season_mean": {k: nan_to_none(v) for k, v in season.items()}}


def heatmap(db: Session, parameter: str, station_ids=None, start=None, end=None) -> dict:
    w = _filtered(db, station_ids, start, end)
    piv = w.pivot_table(index="dow", columns="hour", values=parameter, aggfunc="mean").reindex(index=range(7),
                                                                                               columns=range(24))
    return {"parameter": parameter, "unit": UNITS[parameter],
            "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "hours": list(range(24)),
            "values": [[nan_to_none(v) for v in row] for row in piv.values]}


def correlation(db: Session, station_ids=None, start=None, end=None, method: str = "spearman") -> dict:
    w = _filtered(db, station_ids, start, end)
    cols = [c for c in POLLUTANT_LABELS if c in w]
    wx = weather_all(db)
    if len(wx):
        w = w.merge(wx, on=["station_id", "ts"], how="left")
        cols += [c for c in WEATHER_LABELS if c in w]
    c = w[cols].corr(method=method, min_periods=500)
    labels = {**POLLUTANT_LABELS, **WEATHER_LABELS}
    return {"method": method, "variables": cols, "labels": [labels[x] for x in cols],
            "matrix": [[nan_to_none(round(v, 3)) for v in row] for row in c.values], "n": int(len(w))}


def distribution(db: Session, parameter: str, station_ids=None, start=None, end=None, by: str = "station") -> dict:
    w = _filtered(db, station_ids, start, end)
    names = station_names(db)
    key = "station_id" if by == "station" else "month"
    out = []
    for k, s in w.groupby(key)[parameter]:
        s = s.dropna()
        if len(s) < 10:
            continue
        q1, med, q3 = s.quantile([0.25, 0.5, 0.75])
        iqr = q3 - q1
        lo, hi = s[s >= q1 - 1.5 * iqr].min(), s[s <= q3 + 1.5 * iqr].max()
        out.append({"key": int(k), "label": names.get(int(k)) if by == "station" else
                    pd.Timestamp(2000, int(k), 1).strftime("%b"), "min": float(lo), "q1": float(q1), "median": float(med),
                    "q3": float(q3), "max": float(hi), "mean": float(s.mean()), "n": int(len(s)),
                    "outliers": int(((s < lo) | (s > hi)).sum())})
    hist, edges = np.histogram(w[parameter].dropna().clip(upper=w[parameter].quantile(0.995)), bins=40)
    return {"parameter": parameter, "unit": UNITS[parameter], "by": by, "groups": out,
            "histogram": {"counts": hist.tolist(), "edges": [round(float(e), 2) for e in edges]}}


def station_comparison(db: Session, parameter: str = "pm25", start=None, end=None) -> dict:
    w = _filtered(db, None, start, end)
    names = station_names(db)
    daily = w.groupby(["station_id", "date"])[parameter].agg(["mean", "count"])
    daily = daily[daily["count"] >= 18]["mean"]
    rows = []
    for sid, s in w.groupby("station_id")[parameter]:
        d = daily.get(sid) if sid in daily.index.get_level_values(0) else pd.Series(dtype=float)
        rows.append({"station_id": int(sid), "name": names.get(int(sid)), "mean": nan_to_none(s.mean()),
                     "median": nan_to_none(s.median()), "p95": nan_to_none(s.quantile(0.95)),
                     "hours": int(s.notna().sum()),
                     "pct_hours_above_threshold": nan_to_none((s > ALERT_THRESHOLD).mean() * 100 if s.notna().any() else None),
                     "days_above_threshold": int((d > ALERT_THRESHOLD).sum()) if len(d) else 0,
                     "valid_days": int(len(d))})
    rows.sort(key=lambda r: -(r["mean"] or 0))
    return {"parameter": parameter, "unit": UNITS[parameter], "threshold": ALERT_THRESHOLD, "stations": rows}


def weather_relationship(db: Session, variable: str, station_ids=None, start=None, end=None, sample: int = 2500) -> dict:
    w = _filtered(db, station_ids, start, end)
    wx = weather_all(db)
    if wx.empty:
        return {"variable": variable, "points": [], "binned": []}
    m = w.merge(wx, on=["station_id", "ts"], how="inner")[["pm25", variable, "month"]].dropna()
    if variable == "precipitation":
        # Rain relationship on DAILY totals is more meaningful than hourly
        d = w.merge(wx, on=["station_id", "ts"]).groupby(["station_id", "date"]).agg(
            pm25=("pm25", "mean"), precipitation=("precipitation", "sum"), month=("month", "first")).dropna()
        m = d
    pts = m.sample(min(sample, len(m)), random_state=0) if len(m) else m
    try:
        bins = pd.qcut(m[variable], 10, duplicates="drop")
        binned = m.groupby(bins, observed=True)["pm25"].agg(["mean", "median", "count"]).reset_index()
        binned_out = [{"x": float(iv.mid), "mean": float(r["mean"]), "median": float(r["median"]), "n": int(r["count"])}
                      for iv, (_, r) in zip(binned[variable], binned.iterrows())]
    except ValueError:
        binned_out = []
    rho = m[["pm25", variable]].corr(method="spearman").iloc[0, 1] if len(m) > 30 else None
    return {"variable": variable, "label": WEATHER_LABELS.get(variable, variable), "spearman": nan_to_none(rho),
            "resolution": "daily" if variable == "precipitation" else "hourly",
            "points": [{"x": float(r[variable]), "y": float(r["pm25"]), "season": SEASON_OF_MONTH[int(r["month"])]}
                       for _, r in pts.iterrows()],
            "binned": binned_out}


def summary(db: Session) -> dict:
    def build():
        w = _filtered(db, None, None, None)
        pm = w["pm25"]
        return {"period_start": w.ts.min().isoformat() if len(w) else None,
                "period_end": w.ts.max().isoformat() if len(w) else None,
                "hourly_records": int(pm.notna().sum()), "stations": int(w.station_id.nunique()),
                "pm25_mean": nan_to_none(pm.mean()), "pm25_median": nan_to_none(pm.median()),
                "pm25_p95": nan_to_none(pm.quantile(0.95)),
                "pct_hours_above_threshold": nan_to_none((pm > ALERT_THRESHOLD).mean() * 100)}
    return cached(db, ("summary",), build)


def insights(db: Session) -> dict:
    """Auto-generated, data-driven answers to the core EDA questions. Every number is computed."""
    def build():
        w = _filtered(db, None, None, None)
        out = []
        mm = w.groupby("month")["pm25"].mean().dropna()
        if len(mm):
            worst, best = int(mm.idxmax()), int(mm.idxmin())
            mn = lambda m: pd.Timestamp(2000, m, 1).strftime("%B")
            out.append({"id": "worst_month", "question": "Which months have the highest PM2.5?",
                        "answer": f"{mn(worst)} is the most polluted month on average ({mm.max():.0f} µg/m³) - "
                                  f"{mm.max() / mm.min():.1f}× the cleanest month, {mn(best)} ({mm.min():.0f} µg/m³).",
                        "metric": round(float(mm.max()), 1)})
        sc = station_comparison(db)["stations"]
        if sc:
            top = sc[0]
            out.append({"id": "hotspot", "question": "Which locations are consistently high?",
                        "answer": f"{top['name']} has the highest mean PM2.5 ({top['mean']:.0f} µg/m³) with "
                                  f"{top['days_above_threshold']} days above the 60 µg/m³ NAAQS daily standard.",
                        "metric": round(top["mean"], 1)})
        hh = w.groupby("hour")["pm25"].mean().dropna()
        if len(hh):
            out.append({"id": "peak_hour", "question": "Does pollution vary by time of day?",
                        "answer": f"Yes - PM2.5 peaks around {int(hh.idxmax()):02d}:00 IST ({hh.max():.0f} µg/m³) and is "
                                  f"lowest near {int(hh.idxmin()):02d}:00 IST ({hh.min():.0f} µg/m³), a "
                                  f"{(hh.max() / hh.min() - 1) * 100:.0f}% swing driven by traffic and the nocturnal boundary layer.",
                        "metric": int(hh.idxmax())})
        rain = weather_relationship(db, "precipitation", sample=10)
        if rain["binned"]:
            dry = [b for b in rain["binned"] if b["x"] < 0.5]
            wet = [b for b in rain["binned"] if b["x"] >= 5]
            if dry and wet:
                out.append({"id": "rain", "question": "How does rainfall relate to PM2.5?",
                            "answer": f"Days with ≥5 mm rain average {np.mean([b['mean'] for b in wet]):.0f} µg/m³ vs "
                                      f"{np.mean([b['mean'] for b in dry]):.0f} µg/m³ on dry days (Spearman ρ = "
                                      f"{rain['spearman']:.2f}) - wet scavenging plus monsoon ventilation.",
                            "metric": nan_to_none(rain["spearman"])})
        corr = correlation(db)
        best_pair, best_r = None, 0.0
        v = corr["variables"]
        if "pm25" in v:
            i = v.index("pm25")
            for j, var in enumerate(v):
                r = corr["matrix"][i][j]
                if var in ("pm25", "pm10") or r is None:
                    continue
                if abs(r) > abs(best_r):
                    best_pair, best_r = (corr["labels"][i], corr["labels"][j]), r
        pm10r = corr["matrix"][v.index("pm25")][v.index("pm10")] if "pm10" in v else None
        if pm10r is not None:
            out.append({"id": "pollutant_relationships", "question": "Which pollutants show strong relationships?",
                        "answer": f"PM2.5 and PM10 are strongly linked (ρ = {pm10r:.2f}) - PM2.5 is a subset of PM10. "
                                  + (f"Beyond PM10, the strongest association is {best_pair[0]}–{best_pair[1]} "
                                     f"(ρ = {best_r:.2f})." if best_pair else ""),
                        "metric": pm10r})
        sm = w.assign(season=w.month.map(SEASON_OF_MONTH)).groupby("season")["pm25"].mean()
        if {"winter", "monsoon"} <= set(sm.index):
            out.append({"id": "seasonality", "question": "Are there seasonal patterns?",
                        "answer": f"Strongly: winter averages {sm['winter']:.0f} µg/m³ versus {sm['monsoon']:.0f} µg/m³ in the "
                                  f"monsoon ({sm['winter'] / sm['monsoon']:.1f}×), consistent with winter inversions trapping emissions.",
                        "metric": round(float(sm["winter"] / sm["monsoon"]), 2)})
        return {"insights": out, "generated_from_records": int(w["pm25"].notna().sum())}
    return cached(db, ("insights",), build)


def city_aqi(pm25_mean: float | None) -> tuple[int | None, str | None]:
    return (pm25_sub_index(pm25_mean), aqi_category(pm25_mean)) if pm25_mean is not None else (None, None)
