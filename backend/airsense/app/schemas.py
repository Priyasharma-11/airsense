"""Pydantic request/response models (validation layer of the API contract)."""
from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from airsense.app.core.security import validate_password_strength

T = TypeVar("T")
Pollutant = Literal["pm25", "pm10", "no2", "so2", "co", "o3"]
Resolution = Literal["hour", "day", "month"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class Message(BaseModel):
    message: str


# ---------------- auth / users ----------------
class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if any(c in v for c in "<>{}"):
            raise ValueError("Name contains invalid characters.")
        return v

    @field_validator("password")
    @classmethod
    def _pw(cls, v: str) -> str:
        return validate_password_strength(v)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth2 token type, not a secret
    expires_at: datetime


class UserOut(ORM):
    id: int
    email: EmailStr
    full_name: str
    role: str
    created_at: datetime
    last_login_at: datetime | None = None


class UserUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def _pw(cls, v: str) -> str:
        return validate_password_strength(v)


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ForgotPasswordOut(BaseModel):
    message: str
    dev_reset_token: str | None = Field(default=None, description="Only returned when AIRSENSE_ENV=development")


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def _pw(cls, v: str) -> str:
        return validate_password_strength(v)


class PreferencesOut(ORM):
    default_station_id: int | None
    pm25_threshold: float
    sensitive_group: bool
    notify_in_app: bool
    notify_email: bool
    theme: str


class PreferencesIn(BaseModel):
    default_station_id: int | None = None
    pm25_threshold: float = Field(default=60.0, gt=0, le=500)
    sensitive_group: bool = False
    notify_in_app: bool = True
    notify_email: bool = False
    theme: Literal["light", "dark", "system"] = "system"


# ---------------- stations / measurements ----------------
class StationOut(ORM):
    id: int
    external_id: str
    name: str
    city: str
    provider: str
    latitude: float
    longitude: float
    is_active: bool
    used_in_model: bool
    pm25_coverage_pct: float | None


class LatestReading(BaseModel):
    parameter: str
    value: float | None
    unit: str
    ts: datetime | None


class StationLatest(BaseModel):
    station: StationOut
    observed_at: datetime | None
    pm25: float | None
    aqi: int | None
    category: str | None
    readings: list[LatestReading]
    pm25_24h_mean: float | None
    pm25_change_24h: float | None


class CitySummary(BaseModel):
    observed_at: datetime | None
    stations_reporting: int
    stations_total: int
    pm25_mean: float | None
    pm25_max: float | None
    worst_station: StationOut | None
    aqi: int | None
    category: str | None
    data_lag_hours: float | None


class CurrentOut(BaseModel):
    summary: CitySummary
    stations: list[StationLatest]


class SeriesPoint(BaseModel):
    ts: datetime
    value: float | None
    n: int | None = None


class Series(BaseModel):
    station_id: int
    station_name: str
    parameter: str
    unit: str
    resolution: Resolution
    points: list[SeriesPoint]


class MeasurementRecord(BaseModel):
    ts: datetime
    station_id: int
    station_name: str
    parameter: str
    value: float
    unit: str
    is_imputed: bool
    is_outlier: bool


class WeatherOut(BaseModel):
    ts: datetime
    temperature_2m: float | None
    relative_humidity_2m: float | None
    precipitation: float | None
    wind_speed_10m: float | None
    wind_direction_10m: float | None
    surface_pressure: float | None
    boundary_layer_height: float | None
    source_tag: str


# ---------------- forecasts / models ----------------
class ForecastPointOut(ORM):
    horizon: int
    target_time: datetime
    pm25: float
    lower: float
    upper: float
    p_exceed: float
    category: str | None


class Contribution(BaseModel):
    feature: str
    label: str
    value: float | None
    contribution: float


class ForecastOut(BaseModel):
    station: StationOut
    model_version: str
    issued_at: datetime
    generated_at: datetime
    latest_pm25: float
    threshold: float
    interval_level: float
    points: list[ForecastPointOut]
    explanations: dict[str, list[Contribution]]
    peak: ForecastPointOut
    hours_above_threshold: int
    best_window: dict | None = Field(description="Cleanest consecutive 2-hour window in the forecast")


class ModelVersionOut(ORM):
    version: str
    algorithm: str
    is_active: bool
    trained_at: datetime
    data_hash: str
    metrics: dict | None


# ---------------- alerts ----------------
class AlertRuleIn(BaseModel):
    station_id: int
    name: str = Field(min_length=1, max_length=100)
    threshold: float = Field(default=60.0, gt=0, le=500)
    lookahead_hours: int = Field(default=24, ge=1, le=24)
    min_probability: float = Field(default=0.5, ge=0, le=1)
    is_active: bool = True


class AlertRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    threshold: float | None = Field(default=None, gt=0, le=500)
    lookahead_hours: int | None = Field(default=None, ge=1, le=24)
    min_probability: float | None = Field(default=None, ge=0, le=1)
    is_active: bool | None = None


class AlertRuleOut(ORM):
    id: int
    station_id: int
    name: str
    threshold: float
    lookahead_hours: int
    min_probability: float
    is_active: bool
    created_at: datetime
    station: StationOut


class AlertOut(ORM):
    id: int
    rule_id: int | None
    station_id: int
    kind: str
    severity: str
    title: str
    message: str
    value: float
    threshold: float
    probability: float | None
    target_time: datetime
    is_read: bool
    created_at: datetime
    station: StationOut


class EvaluateOut(BaseModel):
    rules_evaluated: int
    alerts_created: int
    alerts: list[AlertOut]


class IngestionRunOut(ORM):
    id: int
    kind: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    rows_upserted: int
    details: dict | None
