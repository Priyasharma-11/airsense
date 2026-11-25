"""Static EDA report: the 8 required visualisations + machine-readable answers to the EDA questions.

    python -m airsense.ml.eda      ->  reports/figures/eda_*.png, reports/eda_summary.json
(The web app renders the same analyses interactively from the database.)
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from airsense.ml.data_collection import load_station_catalog
from airsense.ml.feature_engineering import SEASON_OF_MONTH
from airsense.ml.paths import FIGURES_DIR, INTERIM_DIR, PROCESSED_DIR, REPORTS_DIR

POLL = ["pm25", "pm10", "no2", "so2", "co", "o3"]
LABEL = {"pm25": "PM2.5", "pm10": "PM10", "no2": "NO₂", "so2": "SO₂", "co": "CO", "o3": "O₃"}


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams.update({"figure.dpi": 120, "axes.spines.top": False, "axes.spines.right": False})
    return plt, sns


def load() -> pd.DataFrame:
    h = pd.read_parquet(PROCESSED_DIR / "hourly_measurements.parquet")
    w = pd.read_parquet(INTERIM_DIR / "weather_hourly.parquet").rename(columns={"datetime_utc": "ts"})
    df = h.merge(w, on=["location_id", "ts"], how="left")
    names = {s.location_id: s.name.split(",")[0].replace("_", " ") for s in load_station_catalog()}
    df["station"] = df.location_id.map(names)
    loc = df.ts.dt.tz_convert("Asia/Kolkata")
    df["hour"], df["dow"], df["month"], df["date"] = loc.dt.hour, loc.dt.day_of_week, loc.dt.month, loc.dt.date
    df["season"] = df.month.map(SEASON_OF_MONTH)
    return df


def run() -> dict:
    plt, sns = _plt()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    df = load()
    out: dict = {}

    # 1. Pollution over time (daily network mean, 7-day rolling)
    daily = df.groupby("date")["pm25"].mean()
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(pd.to_datetime(daily.index), daily.values, lw=0.8, alpha=0.5, label="Daily mean")
    ax.plot(pd.to_datetime(daily.index), daily.rolling(7, min_periods=4).mean(), lw=2, label="7-day mean")
    ax.axhline(60, color="red", ls="--", lw=1, label="NAAQS 24 h (60)")
    ax.set(title="PM2.5 over time - Pune network", ylabel="µg/m³")
    ax.legend()
    fig.tight_layout(); fig.savefig(FIGURES_DIR / "eda_1_timeseries.png"); plt.close(fig)

    # 2. Monthly / seasonal pattern
    monthly = df.groupby("month")["pm25"].agg(["mean", "median", lambda s: s.quantile(0.9)])
    monthly.columns = ["mean", "median", "p90"]
    fig, ax = plt.subplots(figsize=(9, 4))
    for c in monthly:
        ax.plot(monthly.index, monthly[c], marker="o", label=c)
    ax.set(title="Seasonal pattern of PM2.5 (calendar month)", xlabel="Month", ylabel="µg/m³", xticks=range(1, 13))
    ax.legend(); fig.tight_layout(); fig.savefig(FIGURES_DIR / "eda_2_seasonal.png"); plt.close(fig)
    out["highest_months"] = monthly["mean"].sort_values(ascending=False).head(3).round(1).to_dict()
    out["season_mean"] = df.groupby("season")["pm25"].mean().round(1).to_dict()

    # 3. Hourly heatmap (weekday x hour)
    piv = df.pivot_table(index="dow", columns="hour", values="pm25", aggfunc="mean")
    piv.index = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    fig, ax = plt.subplots(figsize=(12, 3.6))
    sns.heatmap(piv, cmap="YlOrRd", ax=ax, cbar_kws={"label": "µg/m³"})
    ax.set(title="Mean PM2.5 by weekday and hour (IST)", xlabel="Hour", ylabel="")
    fig.tight_layout(); fig.savefig(FIGURES_DIR / "eda_3_hourly_heatmap.png"); plt.close(fig)
    hourly = df.groupby("hour")["pm25"].mean()
    out["peak_hour_ist"], out["min_hour_ist"] = int(hourly.idxmax()), int(hourly.idxmin())

    # 4. Correlation matrix
    cols = POLL + ["temperature_2m", "relative_humidity_2m", "wind_speed_10m", "boundary_layer_height", "precipitation"]
    corr = df[cols].corr(method="spearman")
    fig, ax = plt.subplots(figsize=(8, 7))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0, vmin=-1, vmax=1, ax=ax, annot_kws={"size": 7})
    ax.set_title("Spearman correlation - pollutants and weather")
    fig.tight_layout(); fig.savefig(FIGURES_DIR / "eda_4_correlation.png"); plt.close(fig)
    out["pm25_correlations"] = corr["pm25"].drop("pm25").round(3).sort_values(key=abs, ascending=False).to_dict()

    # 5. Station comparison
    st = df.groupby("station")["pm25"].mean().sort_values()
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(st.index, st.values, color="#12b89a")
    ax.axvline(df.pm25.mean(), color="k", ls="--", lw=1, label="Network mean")
    ax.set(title="Mean PM2.5 by station", xlabel="µg/m³"); ax.legend()
    fig.tight_layout(); fig.savefig(FIGURES_DIR / "eda_5_stations.png"); plt.close(fig)
    out["station_mean"] = st.sort_values(ascending=False).round(1).to_dict()

    # 6. Distribution (box plot by station, log axis to show the heavy tail)
    fig, ax = plt.subplots(figsize=(10, 5))
    order = st.index[::-1]
    sns.boxplot(data=df, y="station", x="pm25", order=order, ax=ax, fliersize=1, color="#9ee5d6")
    ax.set(xscale="log", title="PM2.5 distribution by station (log scale)", xlabel="µg/m³", ylabel="")
    fig.tight_layout(); fig.savefig(FIGURES_DIR / "eda_6_boxplot.png"); plt.close(fig)

    # 7. Geographic distribution (static; the app has the interactive Leaflet map)
    geo = df.groupby(["station", "location_id"]).agg(pm25=("pm25", "mean")).reset_index()
    cat = {s.location_id: (s.latitude, s.longitude) for s in load_station_catalog()}
    geo["lat"], geo["lon"] = zip(*geo.location_id.map(cat))
    fig, ax = plt.subplots(figsize=(7, 6))
    sc = ax.scatter(geo.lon, geo.lat, s=geo.pm25 * 12, c=geo.pm25, cmap="YlOrRd", edgecolor="k")
    for _, r in geo.iterrows():
        ax.annotate(r.station, (r.lon, r.lat), fontsize=7, xytext=(5, 5), textcoords="offset points")
    plt.colorbar(sc, label="mean PM2.5 µg/m³")
    ax.set(title="Station locations and mean PM2.5", xlabel="Longitude", ylabel="Latitude")
    fig.tight_layout(); fig.savefig(FIGURES_DIR / "eda_7_geographic.png"); plt.close(fig)

    # 8. PM2.5 vs weather
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    s = df.dropna(subset=["pm25"]).sample(6000, random_state=0)
    axes[0].scatter(s.wind_speed_10m, s.pm25, s=3, alpha=0.3); axes[0].set(xlabel="Wind speed (km/h)", ylabel="PM2.5", yscale="log")
    axes[1].scatter(s.boundary_layer_height, s.pm25, s=3, alpha=0.3); axes[1].set(xlabel="Boundary-layer height (m)", yscale="log")
    d = df.groupby(["location_id", "date"]).agg(pm25=("pm25", "mean"), rain=("precipitation", "sum")).dropna()
    axes[2].scatter(d.rain, d.pm25, s=4, alpha=0.4); axes[2].set(xlabel="Daily rainfall (mm)", yscale="log")
    fig.suptitle("PM2.5 versus meteorology"); fig.tight_layout(); fig.savefig(FIGURES_DIR / "eda_8_weather.png"); plt.close(fig)
    out["rain_effect"] = {"dry_days_mean": round(float(d[d.rain < 0.5].pm25.mean()), 1),
                          "wet_days_mean_ge5mm": round(float(d[d.rain >= 5].pm25.mean()), 1),
                          "spearman_daily": round(float(d[["pm25", "rain"]].corr("spearman").iloc[0, 1]), 3)}

    out["records"] = int(df.pm25.notna().sum())
    out["period"] = [str(df.ts.min()), str(df.ts.max())]
    (REPORTS_DIR / "eda_summary.json").write_text(json.dumps(out, indent=2, default=lambda o: float(o) if isinstance(o, np.floating) else str(o)))
    return out


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))
