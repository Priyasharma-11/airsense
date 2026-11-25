"""Threshold-based alerting from probabilistic forecasts and from observations.

A rule fires when, within its look-ahead window, the forecast probability of exceeding the user's
threshold is >= ``min_probability`` (calibrated from validation residuals). One alert per rule per
pollution episode: alerts within +/- 6 h of an existing one for the same station are de-duplicated.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from airsense.app.core.errors import AppError
from airsense.app.db.models import Alert, AlertRule, Measurement, User
from airsense.app.services import forecasting
from airsense.app.services.notify import send_email
from airsense.ml.evaluation import aqi_category

log = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")
DEDUPE_WINDOW = timedelta(hours=6)


def _fmt(t) -> str:
    return t.astimezone(IST).strftime("%H:%M IST, %d %b")


def _is_duplicate(db: Session, user_id: int, station_id: int, kind: str, target) -> bool:
    return db.scalar(select(Alert.id).where(Alert.user_id == user_id, Alert.station_id == station_id,
                                            Alert.kind == kind, Alert.target_time >= target - DEDUPE_WINDOW,
                                            Alert.target_time <= target + DEDUPE_WINDOW)) is not None


def evaluate_rules(db: Session, user: User | None = None) -> tuple[int, list[Alert]]:
    q = select(AlertRule).where(AlertRule.is_active)
    if user is not None:
        q = q.where(AlertRule.user_id == user.id)
    rules = db.execute(q).scalars().all()
    created: list[Alert] = []
    forecasts = {}
    for rule in rules:
        try:
            fc = forecasts.get(rule.station_id) or forecasting.get_forecast(db, rule.station_id)
        except AppError as e:
            log.warning("rule %s skipped: %s", rule.id, e.message)
            continue
        forecasts[rule.station_id] = fc
        window = [p for p in sorted(fc.points, key=lambda p: p.horizon) if p.horizon <= rule.lookahead_hours]
        hits = [(p, forecasting.probability_for(fc, p, rule.threshold)) for p in window]
        hits = [(p, pr) for p, pr in hits if pr >= rule.min_probability]
        new: list[Alert] = []
        if hits:
            peak, prob = max(hits, key=lambda x: x[0].pm25)
            if not _is_duplicate(db, rule.user_id, rule.station_id, "forecast_exceedance", peak.target_time):
                cat = aqi_category(peak.pm25) or "Unknown"
                new.append(Alert(
                    user_id=rule.user_id, rule_id=rule.id, station_id=rule.station_id, kind="forecast_exceedance",
                    severity=cat, value=round(peak.pm25, 1), threshold=rule.threshold, probability=prob,
                    target_time=peak.target_time,
                    title=f"{rule.station.name.split(',')[0]}: PM2.5 expected above {rule.threshold:.0f} µg/m³",
                    message=(f"PM2.5 at {rule.station.name} is forecast to peak near {peak.pm25:.0f} µg/m³ ({cat}) "
                             f"around {_fmt(peak.target_time)}. Probability of exceeding your "
                             f"{rule.threshold:.0f} µg/m³ threshold: {prob * 100:.0f}% "
                             f"(model {fc.model_version.version}).")))
        latest = db.scalar(select(Measurement).where(Measurement.station_id == rule.station_id,
                                                     Measurement.parameter == "pm25")
                           .order_by(Measurement.ts.desc()).limit(1))
        if latest and latest.value > rule.threshold and not _is_duplicate(
                db, rule.user_id, rule.station_id, "observed_exceedance", latest.ts):
            cat = aqi_category(latest.value) or "Unknown"
            new.append(Alert(
                user_id=rule.user_id, rule_id=rule.id, station_id=rule.station_id, kind="observed_exceedance",
                severity=cat, value=round(latest.value, 1), threshold=rule.threshold, probability=None,
                target_time=latest.ts, title=f"{rule.station.name.split(',')[0]}: PM2.5 above {rule.threshold:.0f} µg/m³ now",
                message=(f"Observed PM2.5 at {rule.station.name} was {latest.value:.0f} µg/m³ ({cat}) at "
                         f"{_fmt(latest.ts)}, above your {rule.threshold:.0f} µg/m³ threshold.")))
        for a in new:
            try:
                with db.begin_nested():
                    db.add(a)
                created.append(a)
            except IntegrityError:
                continue
        db.commit()
    for a in created:
        u = db.get(User, a.user_id)
        if u and u.preferences and u.preferences.notify_email:
            send_email(u.email, f"AirSense alert - {a.title}", a.message)
    return len(rules), created
