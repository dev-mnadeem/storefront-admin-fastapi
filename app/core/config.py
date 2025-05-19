"""Application settings.

Every value has a default so the API boots with no `.env` file: the default
database is a local SQLite file. Point `DATABASE_URL` at MySQL for the real
deployment (see `.env.example`).
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- database -------------------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./storefront_admin.db"
    sql_echo: bool = False

    # --- http -----------------------------------------------------------
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # --- auth -----------------------------------------------------------
    # When unset, mutating endpoints are open. Set it in any deployment.
    admin_api_key: str | None = None
    api_key_header: str = "X-API-Key"

    # --- listing limits -------------------------------------------------
    default_page_size: int = 50
    max_page_size: int = 200

    # --- inventory ------------------------------------------------------
    low_stock_threshold: int = 10

    # --- insights -------------------------------------------------------
    insight_provider: Literal["rules", "anthropic"] = "rules"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5"
    insight_max_tokens: int = 1024

    @field_validator("admin_api_key", "anthropic_api_key", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: str | None) -> str | None:
        """An empty env var (``ADMIN_API_KEY=``) means "not configured"."""
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
