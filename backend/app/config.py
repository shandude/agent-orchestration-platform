"""Application configuration.

All runtime configuration is sourced from environment variables (or a local
`.env` file) so that no secrets are ever hard-coded. We use pydantic-settings
so the values are validated and typed at startup.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed view over the process environment."""

    model_config = SettingsConfigDict(
        # Look for a .env at the repo root as well as the backend dir so the
        # app works whether launched from Docker or `uvicorn` locally.
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM ────────────────────────────────────────────────────────
    google_api_key: str = ""
    default_model: str = "gemini-2.5-flash"

    # ── Messaging ──────────────────────────────────────────────────
    telegram_bot_token: str = ""

    # ── Infrastructure ─────────────────────────────────────────────
    database_url: str = "sqlite:///./data/orchestrator.db"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    max_graph_iterations: int = 25

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token.strip())

    @property
    def llm_enabled(self) -> bool:
        return bool(self.google_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    """Cached singleton accessor (so we parse the environment only once)."""
    return Settings()
