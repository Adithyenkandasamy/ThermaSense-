"""Shared FastAPI dependencies."""

from app.core.config import Settings, get_settings


def get_app_settings() -> Settings:
    """Dependency-injectable settings accessor."""
    return get_settings()
