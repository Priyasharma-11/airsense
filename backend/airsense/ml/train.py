"""Train, compare and version PM2.5 forecasting models.

Models (direct multi-horizon strategy: one model per horizon h = 1..24 h):
  * Persistence           yhat(t+h) = pm25(t)
  * Seasonal naive        yhat(t+h) = pm25(t+h-24)          (same hour yesterday)
  * Linear Regression     median-impute + standardise + OLS
  * Random Forest         evaluated at key horizons (1, 3, 6, 12, 24) - see docs for cost reasoning
  * XGBoost               early-stopped on validation, refit on train+val for production
  * CAMS (external)       Copernicus CAMS global model PM2.5 at the station grid cell - benchmark only
  * SARIMA (daily track)  daily-mean PM2.5, 1-day-ahead, vs. daily persistence

Splits are strictly chronological with *purging*: training rows whose target time falls inside the
validation/test window are removed, so no label from the future leaks into fitting.
"""
from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import time
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from airsense.ml import evaluation as ev
from airsense.ml.feature_engineering import HORIZONS, add_targets, base_feature_columns, build_features, design_matrix
from airsense.ml.paths import FIGURES_DIR, INTERIM_DIR, MODELS_DIR, PROCESSED_DIR, REPORTS_DIR, RESULTS_DIR

log = logging.getLogger(__name__)

# Chronological split boundaries (UTC). Chosen after the coverage audit - see docs/ML_PIPELINE.md
VAL_START = pd.Timestamp("2026-04-01", tz="UTC")
TEST_START = pd.Timestamp("2026-08-01", tz="UTC")
RF_HORIZONS = [1, 3, 6, 12, 24]
KEY_HORIZONS = [1, 3, 6, 12, 24]
INTERVAL_ALPHA = 0.2  # 80 % prediction intervals
SEED = 42


@dataclass
class Dataset:
    frame: pd.DataFrame       # pooled features + targets + ts + location_id
    feature_cols: list[str]


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame | None]:
    hourly = pd.read_parquet(PROCESSED_DIR / "hourly_measurements.parquet")
    weather = pd.read_parquet(INTERIM_DIR / "weather_hourly.parquet") if (INTERIM_DIR / "weather_hourly.parquet").exists() else None
    cams = pd.read_parquet(INTERIM_DIR / "cams_hourly.parquet") if (INTERIM_DIR / "cams_hourly.parquet").exists() else None
    return hourly, weather, cams


def build_dataset(hourly: pd.DataFrame, weather: pd.DataFrame | None, station_ids: list[int]) -> Dataset:
    frames = []
    for sid in station_ids:
        h = hourly[hourly.location_id == sid]
        w = weather[weather.location_id == sid] if weather is not None else None
        f = build_features(h, w)
        f = add_targets(f, h.set_index("ts")["pm25"], h.set_index("ts")["pm25_imputed"])
        f["location_id"] = sid
        frames.append(f.reset_index())
    df = pd.concat(frames, ignore_index=True)
    feats = base_feature_columns(df.drop(columns=["ts"]))
    return Dataset(df, feats)


def split_masks(df: pd.DataFrame, h: int) -> dict[str, np.ndarray]:
    ts, target_ts = df["ts"], df["ts"] + pd.Timedelta(hours=h)
    return {
        "train": (target_ts < VAL_START).values,                      # purged
        "val": ((ts >= VAL_START) & (target_ts < TEST_START)).values,  # purged
        "trainval": (target_ts < TEST_START).values,
        "test": (ts >= TEST_START).values,
    }


def _eligible(df: pd.DataFrame, h: int) -> np.ndarray:
    # Same rows for every model: observed target and a known latest observation
    return (df[f"y_{h}"].notna() & df["pm25_lag0"].notna()).values


def _seasonal_naive(df: pd.DataFrame, h: int) -> np.ndarray:
    # pm25(t + h - 24) is known at issue time t for h <= 24
    lag = 24 - h
    col = "pm25_lag0" if lag == 0 else f"pm25_lag{lag}"
    if col in df:
        return df[col].values
    # fall back to shifting the observed series per station
    return df.groupby("location_id")["pm25_lag0"].shift(lag).values


def interval_scale(df: pd.DataFrame) -> np.ndarray:
    """Local volatility used to normalise conformal scores (shared with predict.py)."""
    return (df["pm25_rstd24"].fillna(df["pm25_rstd24"].median()) + 5.0).values


def xgb_params() -> dict:
    return dict(n_estimators=3000, learning_rate=0.03, max_depth=6, min_child_weight=5, subsample=0.8,
                colsample_bytree=0.7, reg_lambda=1.0, tree_method="hist", objective="reg:squarederror",
                random_state=SEED, n_jobs=-1, early_stopping_rounds=100, eval_metric="mae")


def train_all(fast: bool = False) -> dict:
    t0 = time.time()
    hourly, weather, cams = load_inputs()
    sel = pd.read_csv(REPORTS_DIR / "data_quality" / "station_selection.csv")
    station_ids = sel.loc[sel.selected_for_model, "location_id"].astype(int).tolist()
    log.info("model stations: %s", station_ids)
    ds = build_dataset(hourly, weather, station_ids)
    df, feats = ds.frame, ds.feature_cols
    horizons = KEY_HORIZONS if fast else HORIZONS
    log.info("pooled rows=%d features=%d", len(df), len(feats))

    cams_map = None
    if cams is not None and len(cams):
        cams_map = cams.set_index(["location_id", "datetime_utc"])["cams_pm25"]

    rows, preds_store, boosters, linear_models, conformal, best_iters = [], {}, {}, {}, {}, {}
    target_modes: dict[int, str] = {}
    shap_importance = None

    for h in horizons:
        m = split_masks(df, h)
        ok = _eligible(df, h)
        X = design_matrix(df, h, feats)
        y = df[f"y_{h}"].values
        tr, va, tv, te = m["train"] & ok, m["val"] & ok, m["trainval"] & ok, m["test"] & ok

        def record(model: str, yhat: np.ndarray, split: str, mask: np.ndarray, extra: dict | None = None,
                   y=y, h=h):
            r = ev.regression_metrics(y[mask], yhat[mask])
            r.update({"model": model, "horizon": h, "split": split})
            if split == "test":
                r["alert"] = ev.alert_metrics(y[mask], yhat[mask])
            if extra:
                r.update(extra)
            rows.append(r)

        persist = df["pm25_lag0"].values
        snaive = _seasonal_naive(df, h)
        for split, mask in (("val", va), ("test", te)):
            record("Persistence", persist, split, mask)
            record("Seasonal naive (24h)", snaive, split, mask)

        # Learned models predict the CHANGE from the latest observation (delta target):
        # yhat = pm25(t) + f(X). Trees cannot extrapolate beyond training levels; learning the delta
        # lets them follow unprecedented episodes (e.g. Diwali 2026, ~1000 ug/m3) like persistence does.
        d = y - persist

        # Linear regression -------------------------------------------------------------
        lr = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LinearRegression())
        lr.fit(X[tr], d[tr])
        record("Linear Regression", persist + lr.predict(X), "val", va)
        lr_tv = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LinearRegression()).fit(X[tv], d[tv])
        lr_test = persist + lr_tv.predict(X)
        record("Linear Regression", lr_test, "test", te)
        linear_models[h] = lr_tv

        # Random forest (key horizons) ------------------------------------------------
        if h in RF_HORIZONS:
            rf_kw = dict(n_estimators=150 if not fast else 60, max_depth=20, min_samples_leaf=5, max_features=0.5,
                         max_samples=0.4, n_jobs=-1, random_state=SEED)
            rf = make_pipeline(SimpleImputer(strategy="median"), RandomForestRegressor(**rf_kw)).fit(X[tr], d[tr])
            record("Random Forest", persist + rf.predict(X), "val", va)
            rf_tv = make_pipeline(SimpleImputer(strategy="median"), RandomForestRegressor(**rf_kw)).fit(X[tv], d[tv])
            record("Random Forest", persist + rf_tv.predict(X), "test", te)

        # XGBoost ---------------------------------------------------------------------
        p = xgb_params()
        if fast:
            p["n_estimators"] = 600
        # Target mode (level vs delta) is a hyper-parameter chosen per horizon on VALIDATION MAE.
        cand = {}
        for mode in ("delta", "level"):
            tgt = d if mode == "delta" else y
            base = persist if mode == "delta" else 0.0
            mdl = xgb.XGBRegressor(**p).fit(X[tr], tgt[tr], eval_set=[(X[va], tgt[va])], verbose=False)
            vp = base + mdl.predict(X)
            cand[mode] = (np.nanmean(np.abs(vp[va] - y[va])), mdl, vp)
        mode = min(cand, key=lambda k: cand[k][0])
        _, model, val_pred = cand[mode]
        target_modes[h] = mode
        best = int(model.best_iteration) + 1
        best_iters[h] = best
        record("XGBoost", val_pred, "val", va, {"best_iteration": best, "target_mode": mode,
                                                 "val_mae_delta": float(cand["delta"][0]),
                                                 "val_mae_level": float(cand["level"][0])})

        # Normalised split-conformal intervals: score = residual / local volatility scale,
        # calibrated on the held-out validation window -> intervals widen in volatile periods.
        scale = interval_scale(df)
        score = ((y[va] - val_pred[va]) / scale[va]).astype(float)
        conformal[h] = {"quantiles": np.quantile(score, np.linspace(0, 1, 101)).tolist(),
                        "lo": float(np.quantile(score, INTERVAL_ALPHA / 2)),
                        "hi": float(np.quantile(score, 1 - INTERVAL_ALPHA / 2)),
                        "n": int(len(score)), "scale": "pm25_rstd24 + 5 (ug/m3)"}

        p_final = {k: v for k, v in p.items() if k != "early_stopping_rounds"}
        p_final["n_estimators"] = max(50, int(best * 1.1))
        tgt = d if mode == "delta" else y
        final = xgb.XGBRegressor(**p_final).fit(X[tv], tgt[tv], verbose=False)
        boosters[h] = final
        yhat = np.clip((persist if mode == "delta" else 0.0) + final.predict(X), 0, None)
        lo = np.clip(yhat + conformal[h]["lo"] * scale, 0, None)
        hi = yhat + conformal[h]["hi"] * scale
        record("XGBoost", yhat, "test", te,
               {"interval_coverage_80": ev.interval_coverage(y[te], lo[te], hi[te]),
                "interval_mean_width": float(np.nanmean((hi - lo)[te]))})

        # External physics-based benchmark: CAMS --------------------------------------
        if cams_map is not None:
            key = pd.MultiIndex.from_arrays([df["location_id"], df["ts"] + pd.Timedelta(hours=h)])
            cams_pred = cams_map.reindex(key).values
            for split, mask in (("val", va), ("test", te)):
                mm = mask & ~np.isnan(cams_pred)
                if mm.sum() > 100:
                    record("CAMS global (Copernicus)", cams_pred, split, mm)

        preds_store[h] = pd.DataFrame({  # noqa: E501 - test-window predictions for diagnostics
"ts": df["ts"].values[te], "location_id": df["location_id"].values[te],
                                       "y": y[te], "xgb": yhat[te], "lo": lo[te], "hi": hi[te],
                                       "persistence": persist[te], "lr": lr_test[te]})
        if h == 24 or (fast and h == horizons[-1]):
            contrib = final.get_booster().predict(xgb.DMatrix(X[te]), pred_contribs=True)
            shap_importance = pd.Series(np.abs(contrib[:, :-1]).mean(0), index=X.columns)
        log.info("h=%2d done  xgb best_iter=%d  (%.0fs elapsed)", h, best, time.time() - t0)

    metrics = pd.DataFrame(rows)
    version = _save_artifacts(df, feats, horizons, boosters, linear_models, conformal, best_iters, metrics,
                              station_ids, shap_importance, target_modes)
    _save_reports(metrics, preds_store, shap_importance, version)
    sarima = sarima_daily_track(hourly, station_ids)
    (RESULTS_DIR / "sarima_daily.json").write_text(json.dumps(sarima, indent=2))
    log.info("finished in %.0fs, version=%s", time.time() - t0, version)
    return {"version": version, "metrics": metrics, "sarima": sarima}


# ----------------------------------------------------------------------------------------------
def _git_hash() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL,
                                       cwd=REPORTS_DIR.parent).decode().strip()
    except Exception:
        return None


def _data_hash() -> str:
    h = hashlib.sha256()
    h.update((PROCESSED_DIR / "hourly_measurements.parquet").read_bytes())
    return h.hexdigest()[:12]


def _save_artifacts(df, feats, horizons, boosters, linear_models, conformal, best_iters, metrics, station_ids,
                    shap_importance, target_modes) -> str:
    now = datetime.now(UTC)
    data_hash = _data_hash()
    version = f"v{now:%Y%m%d}-{data_hash[:6]}"
    out = MODELS_DIR / version
    out.mkdir(parents=True, exist_ok=True)
    test = metrics[metrics.split == "test"]
    summary = (test.groupby(["model"])[["mae", "rmse", "r2"]].mean().round(3).reset_index().to_dict(orient="records"))
    bundle = {
        "version": version,
        "created_at": now.isoformat(),
        "algorithm": "XGBoost direct multi-horizon",
        "horizons": list(horizons),
        "feature_columns": feats,
        "design_columns": list(design_matrix(df.head(2), 1, feats).columns),
        "xgb": {h: m for h, m in boosters.items()},
        "linear": linear_models,
        "conformal": conformal,
        "best_iterations": best_iters,
        "target_modes": target_modes,
        "linear_target_mode": "delta",
        "interval_alpha": INTERVAL_ALPHA,
        "train_window": [str(df.ts.min()), str(TEST_START)],
        "split": {"val_start": str(VAL_START), "test_start": str(TEST_START)},
        "stations": station_ids,
        "data_hash": data_hash,
        "git_commit": _git_hash(),
        "library_versions": {"xgboost": xgb.__version__, "pandas": pd.__version__, "numpy": np.__version__},
    }
    joblib.dump(bundle, out / "best_model.pkl", compress=3)
    meta = {k: v for k, v in bundle.items() if k not in ("xgb", "linear", "conformal")}
    meta["test_summary_mean_over_horizons"] = summary
    if shap_importance is not None:
        meta["global_importance_h24"] = shap_importance.sort_values(ascending=False).head(25).round(3).to_dict()
    (out / "metadata.json").write_text(json.dumps(meta, indent=2, default=str))
    metrics.to_json(out / "metrics.json", orient="records", indent=1)

    reg_path = MODELS_DIR / "registry.json"
    reg = json.loads(reg_path.read_text()) if reg_path.exists() else {"active": None, "versions": []}
    reg["versions"] = [v for v in reg["versions"] if v["version"] != version]
    reg["versions"].append({"version": version, "created_at": now.isoformat(), "path": f"{version}/best_model.pkl",
                            "data_hash": data_hash, "horizons": len(horizons)})
    reg["active"] = version
    reg_path.write_text(json.dumps(reg, indent=2))
    return version


def _save_reports(metrics: pd.DataFrame, preds: dict, shap_importance, version: str) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(RESULTS_DIR / "metrics_long.csv", index=False)
    # Hold-out test predictions travel with the model version (served by /models/{v}/evaluation)
    for h, p in preds.items():
        if h in KEY_HORIZONS:
            p.to_parquet(MODELS_DIR / version / f"test_predictions_h{h}.parquet", index=False)
    test = metrics[metrics.split == "test"].copy()
    piv = test.pivot_table(index="horizon", columns="model", values="mae").round(2)
    piv.to_csv(RESULTS_DIR / "test_mae_by_horizon.csv")
    persist = test[test.model == "Persistence"].set_index("horizon")["mae"]
    test["skill_vs_persistence"] = test.apply(lambda r: ev.skill_score(r["mae"], persist.get(r["horizon"])), axis=1)
    test.to_csv(RESULTS_DIR / "test_metrics.csv", index=False)
    ev.plot_horizon_curve(test, FIGURES_DIR / "model_mae_by_horizon.png", "mae")
    ev.plot_horizon_curve(test, FIGURES_DIR / "model_rmse_by_horizon.png", "rmse")
    for h in (1, 24):
        if h not in preds:
            continue
        p = preds[h]
        sid = p.groupby("location_id").size().idxmax()
        s = p[p.location_id == sid].sort_values("ts").tail(24 * 30)
        ev.plot_actual_vs_pred(s.ts, s.y, s.xgb, s.lo, s.hi, FIGURES_DIR / f"actual_vs_pred_h{h}.png",
                               f"XGBoost h={h}h - station {sid} - last 30 test days ({version})")
        ev.plot_residuals(p.y.values, p.xgb.values, FIGURES_DIR / f"residuals_h{h}.png", f"XGBoost residuals, h={h}h")
        p.to_parquet(RESULTS_DIR / f"test_predictions_h{h}.parquet", index=False)
    if shap_importance is not None:
        ev.plot_feature_importance(shap_importance, FIGURES_DIR / "feature_importance_h24.png",
                                   "Global feature importance (XGBoost, h=24)")


# ----------------------------------------------------------------------------------------------
def sarima_daily_track(hourly: pd.DataFrame, station_ids: list[int]) -> dict:
    """SARIMA(1,0,1)(1,0,1,7) on daily-mean PM2.5 (days with >= 18 valid hours), 1-day-ahead
    rolling forecasts over the test window without refitting, compared with daily persistence."""
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    res = {}
    for sid in station_ids:
        h = hourly[hourly.location_id == sid].set_index("ts")["pm25"]
        h = h.tz_convert("Asia/Kolkata")
        cnt = h.resample("1D").count()
        d = h.resample("1D").mean().where(cnt >= 18)
        d.index = d.index.tz_localize(None)
        test_start = TEST_START.tz_convert("Asia/Kolkata").tz_localize(None).normalize()
        train, test = d[d.index < test_start], d[d.index >= test_start]
        if train.notna().sum() < 120 or test.notna().sum() < 20:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = SARIMAX(train, order=(1, 0, 1), seasonal_order=(1, 0, 1, 7), trend="c",
                          enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
            full = fit.apply(d)  # same parameters, filtered over the full series -> 1-step-ahead
        pred = full.get_prediction(start=test.index[0]).predicted_mean
        y = test.values
        res[str(sid)] = {
            "n_days": int(np.isfinite(y).sum()),
            "sarima": ev.regression_metrics(y, pred.reindex(test.index).values),
            "persistence": ev.regression_metrics(y, d.shift(1).reindex(test.index).values),
            "aic": float(fit.aic),
        }
    agg = {}
    for model in ("sarima", "persistence"):
        maes = [v[model]["mae"] for v in res.values() if v[model]["mae"] is not None]
        agg[model] = {"mean_mae": float(np.mean(maes)) if maes else None}
    return {"per_station": res, "mean": agg, "spec": "SARIMA(1,0,1)(1,0,1,7)+c on daily means"}


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="key horizons only, fewer trees (CI / smoke test)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    out = train_all(fast=args.fast)
    t = out["metrics"]
    print(t[(t.split == "test") & t.horizon.isin(KEY_HORIZONS)].pivot_table(index="horizon", columns="model",
                                                                          values="mae").round(2))
    print(json.dumps(out["sarima"]["mean"], indent=1))
