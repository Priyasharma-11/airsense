"""Forecast evaluation: regression metrics, skill vs. persistence, threshold-alert metrics,
interval coverage, and diagnostic plots."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ALERT_THRESHOLD = 60.0  # ug/m3 - Indian NAAQS 24-h PM2.5 standard; upper bound of "Satisfactory"

# CPCB National AQI breakpoints for PM2.5 (24-h average, ug/m3)
AQI_BANDS = [
    ("Good", 0, 30, 0, 50, "#2E9E5B"),
    ("Satisfactory", 30, 60, 51, 100, "#9CC64A"),
    ("Moderate", 60, 90, 101, 200, "#F2C94C"),
    ("Poor", 90, 120, 201, 300, "#F2994A"),
    ("Very Poor", 120, 250, 301, 400, "#EB5757"),
    ("Severe", 250, 10_000, 401, 500, "#8E2C48"),
]


def aqi_category(pm25: float | None) -> str | None:
    if pm25 is None or (isinstance(pm25, float) and np.isnan(pm25)):
        return None
    for name, _lo, hi, *_ in AQI_BANDS:
        if pm25 <= hi:
            return name
    return "Severe"


_AQI_C = [0, 30, 60, 90, 120, 250, 380]
_AQI_I = [0, 50, 100, 200, 300, 400, 500]


def pm25_sub_index(pm25: float | None) -> int | None:
    """CPCB PM2.5 sub-index (piecewise-linear between breakpoints, capped at 500).
    Officially defined on 24-h averages; on hourly values it is *indicative* only."""
    if pm25 is None or np.isnan(pm25):
        return None
    return int(round(float(np.interp(max(pm25, 0.0), _AQI_C, _AQI_I))))


def regression_metrics(y: np.ndarray, yhat: np.ndarray) -> dict:
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    m = ~(np.isnan(y) | np.isnan(yhat))
    y, yhat = y[m], yhat[m]
    if len(y) == 0:
        return {"n": 0, "mae": None, "rmse": None, "r2": None, "bias": None}
    err = yhat - y
    ss_res = float(np.sum(err ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return {
        "n": int(len(y)),
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "r2": float(1 - ss_res / ss_tot) if ss_tot > 0 else None,
        "bias": float(np.mean(err)),
    }


def skill_score(model_mae: float, baseline_mae: float) -> float | None:
    if not baseline_mae:
        return None
    return float(1 - model_mae / baseline_mae)


def alert_metrics(y: np.ndarray, yhat: np.ndarray, threshold: float = ALERT_THRESHOLD) -> dict:
    """Treat 'PM2.5 > threshold' as a binary event; evaluate the forecast as a classifier."""
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    m = ~(np.isnan(y) | np.isnan(yhat))
    a, p = y[m] > threshold, yhat[m] > threshold
    tp, fp, fn, tn = int((a & p).sum()), int((~a & p).sum()), int((a & ~p).sum()), int((~a & ~p).sum())
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else None
    return {"threshold": threshold, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": prec, "recall": rec,
            "f1": f1, "event_rate": float(a.mean()) if len(a) else None}


def interval_coverage(y: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float | None:
    y = np.asarray(y, float)
    m = ~np.isnan(y)
    if not m.any():
        return None
    return float(((y[m] >= lo[m]) & (y[m] <= hi[m])).mean())


# ----------------------------------------------------------------------------------------------
# Plots (matplotlib, saved to reports/figures)
# ----------------------------------------------------------------------------------------------
def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"figure.dpi": 120, "axes.spines.top": False, "axes.spines.right": False,
                         "font.size": 10})
    return plt


def plot_horizon_curve(table: pd.DataFrame, path: Path, metric: str = "mae") -> None:
    plt = _plt()
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for model, g in table.groupby("model"):
        g = g.sort_values("horizon")
        ax.plot(g["horizon"], g[metric], marker="o", ms=3, label=model)
    ax.set_xlabel("Forecast horizon (hours)")
    ax.set_ylabel(f"{metric.upper()} (µg/m³)")
    ax.set_title(f"Test-set {metric.upper()} by horizon")
    ax.legend(frameon=False)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_actual_vs_pred(ts, y, yhat, lo, hi, path: Path, title: str) -> None:
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(ts, y, lw=1, color="#1f2937", label="Observed")
    ax.plot(ts, yhat, lw=1, color="#0ea5e9", label="Forecast")
    if lo is not None:
        ax.fill_between(ts, lo, hi, color="#0ea5e9", alpha=0.15, label="80% interval")
    ax.axhline(ALERT_THRESHOLD, color="#ef4444", ls="--", lw=0.8, label="60 µg/m³ (NAAQS)")
    ax.set_ylabel("PM2.5 (µg/m³)")
    ax.set_title(title)
    ax.legend(frameon=False, ncol=4, loc="upper left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_residuals(y, yhat, path: Path, title: str) -> None:
    plt = _plt()
    r = np.asarray(yhat) - np.asarray(y)
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    axes[0].scatter(y, yhat, s=3, alpha=0.3, color="#0ea5e9")
    lim = [0, np.nanpercentile(np.r_[y, yhat], 99.5)]
    axes[0].plot(lim, lim, color="#111827", lw=0.8)
    axes[0].set(xlabel="Observed", ylabel="Predicted", title="Predicted vs observed")
    axes[1].hist(r, bins=80, color="#6366f1", alpha=0.8)
    axes[1].set(title="Residual distribution", xlabel="Predicted − observed")
    axes[2].scatter(yhat, r, s=3, alpha=0.3, color="#f97316")
    axes[2].axhline(0, color="#111827", lw=0.8)
    axes[2].set(title="Residuals vs fitted", xlabel="Predicted", ylabel="Residual")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_feature_importance(imp: pd.Series, path: Path, title: str) -> None:
    plt = _plt()
    imp = imp.sort_values().tail(20)
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.barh(imp.index, imp.values, color="#14b8a6")
    ax.set_title(title)
    ax.set_xlabel("mean |SHAP contribution| (µg/m³)")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
