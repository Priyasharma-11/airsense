"""ML pipeline unit tests: cleaning rules, leakage safety, metrics, inference contract."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from airsense.ml import evaluation as ev
from airsense.ml import preprocessing as pp
from airsense.ml.feature_engineering import add_targets, build_features, design_matrix


def _raw(values, start="2026-01-01T05:30:00+05:30", freq="15min", param="pm25"):
    # 05:30 IST == 00:00 UTC, so 15-min slots align with UTC hour buckets
    ts = pd.date_range(pd.Timestamp(start), periods=len(values), freq=freq)
    return pd.DataFrame({"location_id": 1, "sensors_id": 1, "location": "x", "datetime": ts.map(lambda t: t.isoformat()),
                         "lat": 18.5, "lon": 73.8, "parameter": param, "units": "µg/m³", "value": values})


def _hourly(n=400, seed=0):
    rng = np.random.default_rng(seed)
    ts = pd.date_range("2026-01-01", periods=n, freq="1h", tz="UTC")
    y = 40 + 15 * np.sin(np.arange(n) * 2 * np.pi / 24) + rng.normal(0, 3, n)
    return pd.DataFrame({"ts": ts, "pm25": y, "pm10": y * 1.8, "location_id": 1})


# ------------------------------------------------------------------ preprocessing
def test_impossible_values_removed_and_logged():
    vals = [30.0] * 3 + [-5.0] + [31.0, 32.0, 33.0, 34.0] + [5000.0] + [35.0, 36.0, 37.0]
    q = pp.QualityLog()
    out, _ = pp.clean_station(_raw(vals), 1, q)
    assert out["pm25"].max() < 100
    log = q.frame()
    assert log.loc[log.check == "out_of_physical_bounds", "count"].sum() == 2


def test_flatline_removed():
    vals = list(np.linspace(20, 40, 8)) + [55.0] * (4 * 7) + list(np.linspace(40, 20, 8))  # 7 h stuck sensor
    q = pp.QualityLog()
    out, _ = pp.clean_station(_raw(vals), 1, q)
    assert not (out["pm25"].round(6) == 55.0).any()
    assert q.frame().query("check.str.startswith('flatline')", engine="python")["count"].sum() >= 24


def test_hour_requires_two_valid_slots():
    vals = [10.0, 11.0, 12.0, 13.0, 50.0]   # hour 2 has a single 15-min reading
    out, _ = pp.clean_station(_raw(vals), 1, pp.QualityLog())
    assert out["pm25"].notna().sum() == 1


def test_only_short_gaps_are_interpolated():
    h = [20.0, 21, 22, 23] * 1
    vals = []
    for hour in range(12):
        missing = hour in (3, 6, 7, 8)          # 1-h gap (fillable) and 3-h gap (not fillable)
        vals += [np.nan] * 4 if missing else [20.0 + hour + i * 0.1 for i in range(4)]
    raw = _raw(vals).dropna(subset=["value"])
    out, _ = pp.clean_station(raw, 1, pp.QualityLog())
    assert out["pm25_imputed"].sum() == 1
    assert out["pm25"].isna().sum() == 3
    assert len(h) == 4


# ------------------------------------------------------------------ leakage safety
def test_features_do_not_use_future_values():
    """Changing values AFTER issue time t must not change any feature at t."""
    h = _hourly()
    f1 = build_features(h)
    h2 = h.copy()
    t_idx = 250
    h2.loc[t_idx + 1:, "pm25"] = h2.loc[t_idx + 1:, "pm25"] * 10 + 500
    h2.loc[t_idx + 1:, "pm10"] = 999
    f2 = build_features(h2)
    t = h.ts.iloc[t_idx]
    pd.testing.assert_series_equal(f1.loc[t], f2.loc[t], check_names=False)


def test_targets_are_future_values_and_mask_imputed():
    h = _hourly(60)
    imputed = pd.Series(False, index=h.ts)
    imputed.iloc[10] = True
    f = add_targets(build_features(h), h.set_index("ts")["pm25"], imputed, horizons=[1, 3])
    assert np.isclose(f["y_1"].iloc[5], h.pm25.iloc[6])
    assert np.isclose(f["y_3"].iloc[5], h.pm25.iloc[8])
    assert np.isnan(f["y_1"].iloc[9])  # target hour 10 was interpolated -> excluded


def test_design_matrix_target_calendar_shifts_with_horizon():
    h = _hourly(48)
    f = build_features(h).reset_index()
    cols = ["pm25_lag0"]
    x1, x6 = design_matrix(f, 1, cols), design_matrix(f, 6, cols)
    assert not np.allclose(x1["tgt_hour_sin"].values, x6["tgt_hour_sin"].values)


# ------------------------------------------------------------------ metrics
def test_regression_metrics():
    m = ev.regression_metrics(np.array([1, 2, 3, np.nan]), np.array([1, 2, 5, 4]))
    assert m["n"] == 3 and m["mae"] == pytest.approx(2 / 3) and m["rmse"] == pytest.approx(np.sqrt(4 / 3))


def test_alert_metrics_confusion():
    m = ev.alert_metrics(np.array([10, 70, 80, 20]), np.array([65, 75, 30, 10]), threshold=60)
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (1, 1, 1, 1)
    assert m["precision"] == 0.5 and m["recall"] == 0.5


@pytest.mark.parametrize("v,cat,idx", [(10, "Good", 17), (45, "Satisfactory", 75), (75, "Moderate", 150),
                                        (100, "Poor", 233), (200, "Very Poor", 362), (300, "Severe", 438)])
def test_aqi(v, cat, idx):
    assert ev.aqi_category(v) == cat
    assert ev.pm25_sub_index(v) == idx


def test_interval_coverage():
    assert ev.interval_coverage(np.array([1, 5, 10]), np.array([0, 0, 0]), np.array([2, 6, 8])) == pytest.approx(2 / 3)


# ------------------------------------------------------------------ inference with the real model
def test_forecast_station_contract(seeded):
    from airsense.app.db.session import SessionLocal
    from airsense.app.services.data import station_hourly, station_weather
    from airsense.ml.predict import forecast_station

    db = SessionLocal()
    sid = next(iter(seeded.values()))
    h = station_hourly(db, sid, hours=24 * 9)
    w = station_weather(db, sid, h.ts.min(), h.ts.max())
    db.close()
    res = forecast_station(h, w)
    pts = res["points"]
    assert [p.horizon for p in pts] == list(range(1, 25))
    for p in pts:
        assert 0 <= p.lower <= p.pm25 <= p.upper
        assert 0 <= p.p_exceed <= 1
    assert pts[0].target_time == res["issued_at"] + pd.Timedelta(hours=1)
    assert set(res["explanations"]) == {1, 6, 12, 24}
