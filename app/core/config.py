from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(alias="DATABASE_URL")
    database_url_test: str | None = Field(default=None, alias="DATABASE_URL_TEST")

    schema_name: str = "grants_svc"
    current_user_header: str = "X-User-Id"

    # Used to keep service time consistent within a single request.
    # For production, this stays the system clock.
    now_header: str = "X-Now"

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


settings = Settings()
