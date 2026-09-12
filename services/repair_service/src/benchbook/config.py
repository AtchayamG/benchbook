"""Benchbook Configuration Settings."""

from __future__ import annotations

import json
from typing import Any, Self
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or defaults."""

    model_config = SettingsConfigDict(
        env_prefix="BENCHBOOK_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Benchbook"
    environment: str = Field(
        default="local",
        validation_alias=AliasChoices("BENCHBOOK_ENVIRONMENT", "ENVIRONMENT"),
    )
    database_url: str = Field(
        default="sqlite:///./benchbook.db",
        validation_alias=AliasChoices("BENCHBOOK_DATABASE_URL", "DATABASE_URL"),
    )
    api_prefix: str = "/api"
    milestone: str = Field(
        default="M1",
        validation_alias=AliasChoices("BENCHBOOK_MILESTONE", "MILESTONE"),
    )
    assistant_mode: str = Field(
        default="deterministic",  # deterministic, timeout, busy, unavailable, invalid_output
        validation_alias=AliasChoices("BENCHBOOK_ASSISTANT_MODE", "ASSISTANT_MODE"),
    )
    shop_name: str = "Kovai Tech Bench"
    shop_location: str = "Gandhipuram, Coimbatore, Tamil Nadu"
    shop_phone: str = "+91 98400 11223"
    cors_origins_raw: Any = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
        ],
        validation_alias=AliasChoices("BENCHBOOK_CORS_ORIGINS", "CORS_ORIGINS"),
    )

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Convert postgres:// to postgresql:// for standard driver compatibility."""
        v = v.strip()
        if v.startswith("postgres://"):
            return "postgresql://" + v[len("postgres://") :]
        return v

    @model_validator(mode="after")
    def validate_production_settings(self) -> Self:
        """Enforce strict configuration rules in production:
        1. No silent SQLite fallback: must be valid postgresql:// URL.
        2. Production CORS origins cannot be empty or restricted to localhost/127.0.0.1.
        """
        if self.environment.lower() in ("production", "prod"):
            if (
                not (
                    self.database_url.startswith("postgresql://")
                    or self.database_url.startswith("postgres://")
                )
                or not urlsplit(self.database_url).hostname
                or urlsplit(self.database_url).path in ("", "/")
            ):
                raise ValueError(
                    "Production environment requires a valid PostgreSQL database URL (postgresql://...); "
                    "silent fallback to SQLite is forbidden."
                )
            origins = self.cors_origins
            if not origins:
                raise ValueError(
                    "Production environment requires explicit CORS origins; cannot be empty."
                )
            for origin in origins:
                parsed = urlsplit(origin)
                if (
                    parsed.scheme != "https"
                    or not parsed.hostname
                    or "*" in origin
                    or parsed.hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1")
                    or parsed.username is not None
                    or parsed.password is not None
                    or parsed.path
                    or parsed.query
                    or parsed.fragment
                ):
                    raise ValueError("Production CORS requires explicit non-local HTTPS origins.")
        return self

    @property
    def cors_origins(self) -> list[str]:
        """Parse raw CORS origin input into clean list of allowed origins."""
        v = self.cors_origins_raw
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed: Any = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed if str(x).strip()]
                except Exception:
                    pass
            return [x.strip() for x in v.split(",") if x.strip()]
        if isinstance(v, (list, tuple)):
            return [str(x).strip() for x in v if str(x).strip()]
        return []

    @property
    def is_postgres(self) -> bool:
        """Return True if using a PostgreSQL database."""
        return self.database_url.startswith(("postgresql://", "postgres://"))

    @property
    def is_sqlite(self) -> bool:
        """Return True if using SQLite."""
        return not self.is_postgres

    @property
    def db_engine_name(self) -> str:
        """Return human-readable database engine name."""
        return "postgres" if self.is_postgres else "sqlite"


settings = Settings()
