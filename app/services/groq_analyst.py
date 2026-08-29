"""
Groq AI analyst service.

Uses Groq's `llama-3.1-8b-instant` model to generate fast, intelligent
natural-language summaries for HIGH and EXTREME thermal events.

Each summary includes:
  - Plain-language description of the fire event
  - Key threats (structures, ecosystems, air quality)
  - Recommended action level
  - Confidence assessment

Groq is chosen for its extreme speed (~300 tok/s) — summaries
generate in < 1 second, perfect for real-time event enrichment.
"""

import logging
from typing import Any

from groq import AsyncGroq

from app.models.thermal_event import RiskLevel

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You are ThermaSense AI, an expert wildfire intelligence analyst.
Your role is to analyze satellite-detected thermal event data and produce concise,
actionable intelligence summaries for emergency responders and field teams.

Always respond in valid JSON with exactly these fields:
{
  "summary": "2-3 sentence plain-language description of the event",
  "key_threats": ["threat1", "threat2", "threat3"],
  "recommended_action": "one specific recommended action",
  "confidence_assessment": "brief note on data reliability"
}

Be specific, factual, and avoid generic language. Focus on actionable insights."""


def _build_event_prompt(event_data: dict[str, Any]) -> str:
    """Build the user prompt for a single event."""
    frp = event_data.get("frp")
    brightness = event_data.get("brightness")
    confidence = event_data.get("confidence", "unknown")
    satellite = event_data.get("satellite", "unknown")
    lat = event_data.get("latitude")
    lon = event_data.get("longitude")
    risk_level = event_data.get("risk_level", "HIGH")
    acq_date = event_data.get("acq_date", "unknown")
    acq_time = event_data.get("acq_time", "unknown")
    daynight = "daytime" if event_data.get("daynight") == "D" else "nighttime"

    return f"""Analyze this satellite-detected thermal event:

Location: {lat}°N, {lon}°W
Detection Time: {acq_date} at {acq_time[:2]}:{acq_time[2:]} UTC ({daynight})
Satellite: {satellite}
Risk Level: {risk_level}
Fire Radiative Power (FRP): {frp} MW
Brightness Temperature: {brightness} K
Detection Confidence: {confidence}

Generate an intelligence summary for emergency responders."""


def _build_cluster_prompt(cluster_data: dict[str, Any]) -> str:
    """Build prompt for a regional cluster summary."""
    count = cluster_data.get("event_count", 1)
    max_frp = cluster_data.get("max_frp", 0)
    avg_frp = cluster_data.get("avg_frp", 0)
    region = cluster_data.get("region_name", "Unknown region")
    extreme_count = cluster_data.get("extreme_count", 0)
    high_count = cluster_data.get("high_count", 0)
    lat_center = cluster_data.get("lat_center")
    lon_center = cluster_data.get("lon_center")

    return f"""Analyze this regional wildfire cluster:

Region: {region}
Center: {lat_center}°N, {lon_center}°W
Total Hotspots Detected: {count}
EXTREME risk events: {extreme_count}
HIGH risk events: {high_count}
Maximum FRP: {max_frp} MW
Average FRP: {avg_frp:.1f} MW

Generate a regional intelligence summary for emergency management."""


async def generate_event_summary(
    groq_api_key: str,
    event_data: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Generate an AI summary for a single HIGH/EXTREME thermal event.

    Args:
        groq_api_key: Groq API key from settings.
        event_data:   Dict with event fields (lat, lon, frp, etc.)

    Returns:
        Dict with {summary, key_threats, recommended_action, confidence_assessment}
        or None if Groq call fails.
    """
    if not groq_api_key:
        logger.warning("No Groq API key configured — skipping AI summary")
        return None

    try:
        client = AsyncGroq(api_key=groq_api_key)
        prompt = _build_event_prompt(event_data)

        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=400,
            response_format={"type": "json_object"},
        )

        import json

        content = response.choices[0].message.content
        result = json.loads(content)
        logger.info(
            "Groq summary generated for event at (%s, %s)",
            event_data.get("latitude"),
            event_data.get("longitude"),
        )
        return result

    except Exception as exc:
        logger.error("Groq API error: %s", exc)
        return None


async def generate_cluster_summary(
    groq_api_key: str,
    cluster_data: dict[str, Any],
) -> dict[str, Any] | None:
    """Generate an AI summary for a regional cluster of events."""
    if not groq_api_key:
        return None

    try:
        client = AsyncGroq(api_key=groq_api_key)
        prompt = _build_cluster_prompt(cluster_data)

        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        import json

        return json.loads(response.choices[0].message.content)

    except Exception as exc:
        logger.error("Groq cluster summary error: %s", exc)
        return None


def format_summary_text(groq_result: dict[str, Any] | None) -> str | None:
    """
    Convert Groq JSON result into a single formatted text block
    for storage in the database `ai_summary` column.
    """
    if not groq_result:
        return None

    lines = []

    if summary := groq_result.get("summary"):
        lines.append(summary)

    if threats := groq_result.get("key_threats"):
        threat_list = " | ".join(threats) if isinstance(threats, list) else str(threats)
        lines.append(f"Threats: {threat_list}")

    if action := groq_result.get("recommended_action"):
        lines.append(f"Action: {action}")

    if assessment := groq_result.get("confidence_assessment"):
        lines.append(f"Confidence: {assessment}")

    return "\n".join(lines) if lines else None


# Risk levels that trigger Groq summary generation
GROQ_TRIGGER_LEVELS = {RiskLevel.HIGH, RiskLevel.EXTREME}
