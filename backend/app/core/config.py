"""
ThermaSense application configuration.

Settings are loaded from environment variables / .env file.
All settings are validated at startup via Pydantic.
"""

from functools import lru_cache
from typing import Literal, Union

from pydantic import field_validator
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

    # ── NASA FIRMS ────────────────────────────────────────────────
    # Obtain a free key at https://firms.modaps.eosdis.nasa.gov/api/
    firms_map_key: str = ""

    # ── Monitoring & Scheduler ────────────────────────────────────
    firms_monitoring_enabled: bool = True
    firms_poll_interval_minutes: int = 10
    firms_monitoring_area: str = "76,8,80,13"
    firms_day_range: int = 1
    firms_sources: Union[str, list[str]] = ["VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]

    # ── Reliability & Retries ─────────────────────────────────────
    firms_max_retries: int = 3
    firms_retry_delay_seconds: float = 30.0
    firms_timeout_seconds: int = 60

    # ── Event Clustering ──────────────────────────────────────────
    clustering_spatial_threshold_km: float = 5.0
    clustering_temporal_threshold_hours: float = 24.0

    # ── Database ──────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://thermasense:thermasense@localhost:5432/thermasense"

    @field_validator("firms_sources", mode="after")
    @classmethod
    def parse_firms_sources(cls, v: Union[str, list[str]]) -> list[str]:
        """Convert string or list input to a list of source strings."""
        if isinstance(v, str):
            # Check if it's JSON array string or comma separated
            s_val = v.strip()
            if s_val.startswith("[") and s_val.endswith("]"):
                import json
                try:
                    parsed = json.loads(s_val)
                    if isinstance(parsed, list):
                        return [str(s).strip() for s in parsed if str(s).strip()]
                except Exception:
                    pass
            sources = [s.strip() for s in s_val.split(",") if s.strip()]
            return sources if sources else ["VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]
        if isinstance(v, list):
            return [str(s).strip() for s in v if str(s).strip()]
        return ["VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]


    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()

