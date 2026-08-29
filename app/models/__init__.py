"""ORM models — import all models here so Alembic detects them."""

from app.models.thermal_event import RiskLevel, ThermalEvent

__all__ = ["ThermalEvent", "RiskLevel"]
