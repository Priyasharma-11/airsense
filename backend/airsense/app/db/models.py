"""Normalised relational schema (3NF). See docs/DATABASE.md for the ER diagram.

PostGIS: on PostgreSQL, migration 0001 adds a generated ``stations.geom geography(Point,4326)``
column with a GiST index (derived from latitude/longitude). The ORM keeps plain lat/lon so the same
models run on SQLite for local development and tests; spatial queries switch implementation by dialect.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

POLLUTANTS = ("pm25", "pm10", "no2", "so2", "co", "o3")


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes on every backend (SQLite drops tzinfo)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        value = value.astimezone(UTC)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow,
                                                 server_default=func.now())


class DataSource(Base, TimestampMixin):
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(500))
    license: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(32))  # observation | reanalysis | model_benchmark
    description: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (CheckConstraint("kind in ('observation','reanalysis','model_benchmark')", name="ck_source_kind"),)


class Station(Base, TimestampMixin):
    __tablename__ = "stations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100), index=True)
    provider: Mapped[str] = mapped_column(String(50))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    used_in_model: Mapped[bool] = mapped_column(Boolean, default=False)
    pm25_coverage_pct: Mapped[float | None] = mapped_column(Float)
    first_seen: Mapped[datetime | None] = mapped_column(UTCDateTime)

    source: Mapped[DataSource] = relationship()
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_station_source_external"),
        CheckConstraint("latitude between -90 and 90", name="ck_station_lat"),
        CheckConstraint("longitude between -180 and 180", name="ck_station_lon"),
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(32))  # seed | incremental
    status: Mapped[str] = mapped_column(String(16), default="running")
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    rows_upserted: Mapped[int] = mapped_column(Integer, default=0)
    details: Mapped[dict | None] = mapped_column(JSON)
    triggered_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    __table_args__ = (CheckConstraint("status in ('running','success','failed')", name="ck_ingestion_status"),)


class Measurement(Base):
    """Hourly, quality-controlled pollutant concentrations (long format)."""

    __tablename__ = "measurements"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(UTCDateTime)
    parameter: Mapped[str] = mapped_column(String(8))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    is_imputed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_outlier: Mapped[bool] = mapped_column(Boolean, default=False)
    ingestion_run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id", ondelete="SET NULL"))
    __table_args__ = (
        UniqueConstraint("station_id", "parameter", "ts", name="uq_measurement"),
        Index("ix_measurement_param_ts", "parameter", "ts"),
        CheckConstraint("value >= 0", name="ck_measurement_nonneg"),
        CheckConstraint(f"parameter in {POLLUTANTS}", name="ck_measurement_param"),
    )


class WeatherObservation(Base):
    __tablename__ = "weather_observations"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"))
    ts: Mapped[datetime] = mapped_column(UTCDateTime)
    temperature_2m: Mapped[float | None] = mapped_column(Float)
    relative_humidity_2m: Mapped[float | None] = mapped_column(Float)
    precipitation: Mapped[float | None] = mapped_column(Float)
    wind_speed_10m: Mapped[float | None] = mapped_column(Float)
    wind_direction_10m: Mapped[float | None] = mapped_column(Float)
    surface_pressure: Mapped[float | None] = mapped_column(Float)
    boundary_layer_height: Mapped[float | None] = mapped_column(Float)
    source_tag: Mapped[str] = mapped_column(String(16))  # era5 | analysis
    __table_args__ = (UniqueConstraint("station_id", "ts", name="uq_weather"),)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[str] = mapped_column(String(64), unique=True)
    algorithm: Mapped[str] = mapped_column(String(100))
    artifact_path: Mapped[str] = mapped_column(String(300))
    data_hash: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    trained_at: Mapped[datetime] = mapped_column(UTCDateTime)
    metrics: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Forecast(Base):
    __tablename__ = "forecasts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"))
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id", ondelete="CASCADE"))
    issued_at: Mapped[datetime] = mapped_column(UTCDateTime)  # time of the latest observation used
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    latest_pm25: Mapped[float] = mapped_column(Float)
    interval_scale: Mapped[float] = mapped_column(Float)  # local volatility used for conformal intervals
    explanations: Mapped[dict | None] = mapped_column(JSON)
    points: Mapped[list[ForecastPoint]] = relationship(back_populates="forecast", cascade="all, delete-orphan",
                                                       order_by="ForecastPoint.horizon")
    station: Mapped[Station] = relationship()
    model_version: Mapped[ModelVersion] = relationship()
    __table_args__ = (UniqueConstraint("station_id", "model_version_id", "issued_at", name="uq_forecast"),)


class ForecastPoint(Base):
    __tablename__ = "forecast_points"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    forecast_id: Mapped[int] = mapped_column(ForeignKey("forecasts.id", ondelete="CASCADE"), index=True)
    horizon: Mapped[int] = mapped_column(Integer)
    target_time: Mapped[datetime] = mapped_column(UTCDateTime)
    pm25: Mapped[float] = mapped_column(Float)
    lower: Mapped[float] = mapped_column(Float)
    upper: Mapped[float] = mapped_column(Float)
    p_exceed: Mapped[float] = mapped_column(Float)
    category: Mapped[str | None] = mapped_column(String(20))
    forecast: Mapped[Forecast] = relationship(back_populates="points")
    __table_args__ = (
        UniqueConstraint("forecast_id", "horizon", name="uq_forecast_point"),
        CheckConstraint("horizon between 1 and 72", name="ck_fp_horizon"),
        CheckConstraint("p_exceed between 0 and 1", name="ck_fp_prob"),
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(16), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    preferences: Mapped[UserPreference] = relationship(back_populates="user", uselist=False,
                                                       cascade="all, delete-orphan")
    __table_args__ = (CheckConstraint("role in ('user','admin')", name="ck_user_role"),)


class UserPreference(Base, TimestampMixin):
    __tablename__ = "user_preferences"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    default_station_id: Mapped[int | None] = mapped_column(ForeignKey("stations.id", ondelete="SET NULL"))
    pm25_threshold: Mapped[float] = mapped_column(Float, default=60.0)
    sensitive_group: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_in_app: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_email: Mapped[bool] = mapped_column(Boolean, default=False)
    theme: Mapped[str] = mapped_column(String(10), default="system")
    user: Mapped[User] = relationship(back_populates="preferences")
    __table_args__ = (CheckConstraint("pm25_threshold > 0 and pm25_threshold <= 500", name="ck_pref_threshold"),
                      CheckConstraint("theme in ('light','dark','system')", name="ck_pref_theme"))


class AlertRule(Base, TimestampMixin):
    __tablename__ = "alert_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    threshold: Mapped[float] = mapped_column(Float, default=60.0)
    lookahead_hours: Mapped[int] = mapped_column(Integer, default=24)
    min_probability: Mapped[float] = mapped_column(Float, default=0.5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    station: Mapped[Station] = relationship()
    __table_args__ = (
        CheckConstraint("threshold > 0 and threshold <= 500", name="ck_rule_threshold"),
        CheckConstraint("lookahead_hours between 1 and 24", name="ck_rule_lookahead"),
        CheckConstraint("min_probability between 0 and 1", name="ck_rule_prob"),
    )


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("alert_rules.id", ondelete="SET NULL"))
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32))  # forecast_exceedance | observed_exceedance
    severity: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    value: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    probability: Mapped[float | None] = mapped_column(Float)
    target_time: Mapped[datetime] = mapped_column(UTCDateTime)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    station: Mapped[Station] = relationship()
    __table_args__ = (
        UniqueConstraint("user_id", "station_id", "kind", "target_time", name="uq_alert_dedupe"),
        CheckConstraint("kind in ('forecast_exceedance','observed_exceedance')", name="ck_alert_kind"),
        Index("ix_alert_user_created", "user_id", "created_at"),
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
