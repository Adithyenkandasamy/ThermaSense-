"""
Deterministic thermal event risk classifier.

No ML needed — we use NASA's own fire metrics (FRP, brightness, confidence)
to assign a risk level and numeric score to each hotspot.

Risk levels:
  EXTREME  — frp > 500 MW or brightness > 500 K
  HIGH     — frp > 100 MW or brightness > 450 K (and confidence is not low)
  MODERATE — frp > 10 MW or confidence == "high" or "nominal"
  LOW      — everything else

Score (0–100):
  Weighted combination of normalized FRP + brightness + confidence bonus.
"""

from app.models.thermal_event import RiskLevel
from app.schemas.thermal_event import ThermalEventCreate


def _confidence_score(confidence: str | None) -> float:
    """Map FIRMS confidence string to a numeric bonus (0–20)."""
    mapping = {
        "high": 20.0,
        "nominal": 10.0,
        "low": 0.0,
        # Numeric confidence (MODIS style: 0-100)
    }
    if confidence is None:
        return 5.0
    c = confidence.lower().strip()
    if c in mapping:
        return mapping[c]
    # Numeric confidence
    try:
        return float(c) * 0.2  # 0-100 → 0-20
    except ValueError:
        return 5.0


def classify(event: ThermalEventCreate) -> tuple[RiskLevel, float]:
    """
    Classify a single thermal event.

    Returns:
        (risk_level, risk_score)  where risk_score ∈ [0, 100]
    """
    frp = event.frp or 0.0
    brightness = event.brightness or 0.0
    confidence = event.confidence

    # ── Compute raw score ────────────────────────────────────────────
    # FRP component: log-scale cap at 1000 MW → maps to 0-60
    import math

    frp_component = min(math.log1p(frp) / math.log1p(1000) * 60, 60) if frp > 0 else 0.0

    # Brightness component: 300K baseline (background), 500K = extreme
    # Maps 300-500K → 0-20
    brightness_component = max(0.0, min((brightness - 300) / 200 * 20, 20)) if brightness > 300 else 0.0

    # Confidence component: 0-20
    confidence_component = _confidence_score(confidence)

    risk_score = round(frp_component + brightness_component + confidence_component, 2)
    risk_score = min(risk_score, 100.0)

    # ── Classify by thresholds ───────────────────────────────────────
    if frp > 500 or brightness > 500:
        level = RiskLevel.EXTREME
    elif frp > 100 or brightness > 470:
        level = RiskLevel.HIGH
    elif frp > 10 or brightness > 420 or (confidence or "").lower() in ("high", "nominal"):
        level = RiskLevel.MODERATE
    else:
        level = RiskLevel.LOW

    return level, risk_score


def classify_batch(
    events: list[ThermalEventCreate],
) -> list[tuple[ThermalEventCreate, RiskLevel, float]]:
    """
    Classify a list of events.

    Returns:
        List of (event, risk_level, risk_score) tuples.
    """
    return [(e, *classify(e)) for e in events]
