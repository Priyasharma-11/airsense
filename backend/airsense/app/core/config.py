"""Environment-based configuration (12-factor). All secrets come from env vars / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from airsense.ml.paths import MODELS_DIR, REPO_ROOT

_INSECURE_DEFAULT = "dev-insecure-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_ROOT / ".env", ".env"), env_prefix="AIRSENSE_",
                                      extra="ignore")

    env: Literal["development", "test", "production"] = "development"
    app_name: str = "AirSense API"
    api_prefix: str = "/api/v1"
    database_url: str = f"sqlite:///{(REPO_ROOT / 'airsense.db').as_posix()}"
    secret_key: str = _INSECURE_DEFAULT
    access_token_expire_minutes: int = 60
    jwt_algorithm: str = "HS256"
    cookie_name: str = "airsense_token"
    cookie_secure: bool = False
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])
    rate_limit_default: str = "120/minute"
    rate_limit_auth: str = "10/minute"
    rate_limit_enabled: bool = True
    models_dir: Path = MODELS_DIR
    forecast_cache_minutes: int = 30
    password_reset_expire_minutes: int = 30
    frontend_url: str = "http://localhost:3000"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "AirSense <no-reply@airsense.local>"
    enable_scheduler: bool = False
    ingestion_interval_hours: int = 6
    log_level: str = "INFO"
    openaq_api_key: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("database_url")
    @classmethod
    def _driver(cls, v: str) -> str:
        # Managed providers (Render, Neon, Heroku) hand out postgres:// URLs; use the psycopg 3 driver
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @model_validator(mode="after")
    def _production_guards(self):
        if self.env == "production":
            if self.secret_key == _INSECURE_DEFAULT or len(self.secret_key) < 32:
                raise ValueError("AIRSENSE_SECRET_KEY must be set to a random value of >= 32 chars in production")
            if "cookie_secure" not in self.model_fields_set:  # secure by default; explicit opt-out for http://localhost
                self.cookie_secure = True
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
