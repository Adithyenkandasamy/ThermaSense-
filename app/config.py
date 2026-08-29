"""
ThermaSense application configuration.

Settings are loaded from environment variables / .env file.
All settings are validated at startup — if a required variable is
missing the app will refuse to start with a clear error message.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # ── Database ──────────────────────────────────────────────────
    # Async URL used by the FastAPI app at runtime
    database_url: str = (
        "postgresql+asyncpg://thermasense:thermasense@localhost:5432/thermasense"
    )
    # Sync URL used only by Alembic migrations
    alembic_database_url: str = (
        "postgresql+psycopg2://thermasense:thermasense@localhost:5432/thermasense"
    )

    # ── External APIs ─────────────────────────────────────────────
    firms_api_key: str = ""
    groq_api_key: str = ""

    # ── Background scheduler ─────────────────────────────────────────
    poll_interval_minutes: int = 10  # How often to auto-fetch from FIRMS

    # ── Demo Region (WGS84 bounding box — Western US / California) ─
    demo_bbox_xmin: float = -124.5
    demo_bbox_ymin: float = 32.5
    demo_bbox_xmax: float = -114.0
    demo_bbox_ymax: float = 42.0

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def demo_bbox(self) -> tuple[float, float, float, float]:
        """Return (xmin, ymin, xmax, ymax)."""
        return (
            self.demo_bbox_xmin,
            self.demo_bbox_ymin,
            self.demo_bbox_xmax,
            self.demo_bbox_ymax,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance. Call this everywhere."""
    return Settings()
