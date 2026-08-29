"""Centralized risk thresholds."""

from app.models.thermal_event import RiskLevel


def risk_level_for_score(score: float) -> RiskLevel:
    if score >= 85:
        return RiskLevel.EXTREME
    if score >= 65:
        return RiskLevel.HIGH
    if score >= 35:
        return RiskLevel.MODERATE
    return RiskLevel.LOW
