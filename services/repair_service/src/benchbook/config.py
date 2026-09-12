"""Benchbook Configuration Settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or defaults."""

    model_config = SettingsConfigDict(env_prefix="BENCHBOOK_", env_file=".env", extra="ignore")

    app_name: str = "Benchbook"
    environment: str = "local"
    database_url: str = "sqlite:///./benchbook.db"
    api_prefix: str = "/api"
    assistant_mode: str = (
        "deterministic"  # deterministic, timeout, busy, unavailable, invalid_output
    )
    shop_name: str = "Kovai Tech Bench"
    shop_location: str = "Gandhipuram, Coimbatore, Tamil Nadu"
    shop_phone: str = "+91 98400 11223"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]


settings = Settings()
