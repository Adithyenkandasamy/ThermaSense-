"""
Groq AI investigation service.

Receives a COMPLETE investigation packet from the backend
(context, history, classification, risk) and asks the AI to
EXPLAIN the evidence — NOT to invent any facts.

The prompt explicitly forbids the model from fabricating:
  - facility names or distances
  - land-cover values
  - FRP / brightness numbers
  - historical observations
  - risk scores

Model: llama-3.1-8b-instant (Groq, ~300 tok/s — fast enough for real-time use)

Fallback: if Groq is unavailable, generates a deterministic explanation
from the same packet, clearly marked AI_MODE=FALLBACK.

Results are stored as structured JSON in EventAnalysis — the frontend
should NEVER trigger a new LLM call on every page view.
"""

import json
import logging
from typing import Any

from app.models.thermal_event import RiskLevel

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.1-8b-instant"

# Risk levels that trigger AI investigation
GROQ_TRIGGER_LEVELS = {RiskLevel.HIGH, RiskLevel.EXTREME, RiskLevel.MODERATE}


# ── System prompt ──────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are ThermaSense AI, an expert industrial thermal event intelligence analyst.

Your role is to analyse satellite-detected thermal events using ONLY the
structured evidence supplied to you. You must NOT invent, assume, or infer
any of the following:
  - Facility names, types, or distances
  - Land-cover classifications
  - FRP values, brightness temperatures, or sensor readings
  - Historical detection counts or baseline FRP values
  - Anomaly ratios or persistence scores
  - Risk scores or classifications

All facts come from the investigation packet. Your job is to EXPLAIN
what the evidence means, not to create new evidence.

Respond with valid JSON only, using exactly these fields:
{
  "summary": "2-3 sentence plain-language description of what is happening",
  "situation": "1-2 sentence statement of the immediate situation",
  "reasoning": [
    "Specific reasoning point citing actual evidence from the packet",
    "Another reasoning point",
    "Third reasoning point (add more as needed)"
  ],
  "assessment": "Overall assessment of the event significance",
  "recommended_action": "One specific, actionable investigation recommendation",
  "confidence_assessment": "Assessment of how reliable this conclusion is given the available evidence"
}

Be specific. Cite the actual numbers from the packet. Avoid generic language.
Focus on what an emergency operator or field team needs to know.
"""


def _build_investigation_prompt(packet: dict[str, Any]) -> str:
    """
    Build a detailed investigation prompt from the evidence packet.

    Every value in the prompt comes from the packet — nothing is invented.
    """
    event = packet.get("event", {})
    geo = packet.get("geographic_context", {})
    hist = packet.get("historical_context", {})
    cls = packet.get("classification", {})
    risk = packet.get("risk", {})

    # Format nearby facilities
    facilities_str = "None detected within search radius"
    facilities = geo.get("nearby_facilities", [])
    if facilities:
        fac_lines = []
        for f in facilities[:5]:  # limit to 5 nearest
            fac_lines.append(
                f"  • {f.get('name', 'Unknown')} ({f.get('type', 'UNKNOWN')}) "
                f"— {f.get('distance_km', '?'):.2f} km away"
            )
        facilities_str = "\n".join(fac_lines)

    # Format historical context
    has_history = hist.get("has_history", False)
    if has_history:
        baseline = hist.get("historical_baseline")
        anomaly = hist.get("anomaly_ratio")
        max_frp_h = hist.get("maximum_frp")
        baseline_str = (f"{baseline:.1f} MW") if baseline is not None else "N/A"
        max_frp_str = (f"{max_frp_h:.1f} MW") if max_frp_h is not None else "N/A"
        anomaly_str = (f"{anomaly:.2f}x baseline") if anomaly is not None else "N/A (no baseline)"
        hist_str = (
            f"  Detections (7d/30d/90d): {hist.get('detections_7d')}/{hist.get('detections_30d')}/{hist.get('detections_90d')}\n"
            f"  Active days (last 90d): {hist.get('active_days')}\n"
            f"  Historical avg FRP: {baseline_str}\n"
            f"  Historical max FRP: {max_frp_str}\n"
            f"  Anomaly ratio: {anomaly_str}\n"
            f"  Persistence score: {hist.get('persistence_score', 0):.2f} (0=never, 1=every day)"
        )
    else:
        hist_str = "  No historical thermal activity at this location in the last 90 days."

    # Format rules fired
    rules = cls.get("rules_fired", [])
    rules_str = "\n  ".join(rules) if rules else "No classification rules triggered"

    daynight_label = "Daytime" if event.get("daynight") == "D" else "Nighttime"
    confidence_label = event.get("confidence", "unknown")

    return f"""THERMAL EVENT INVESTIGATION PACKET

=== EVENT ===
Location: {event.get('latitude')}°, {event.get('longitude')}°
Date/Time: {event.get('acq_date')} at {event.get('acq_time', '????')[:2]}:{event.get('acq_time', '????')[2:]} UTC ({daynight_label})
Satellite: {event.get('satellite', 'Unknown')} / {event.get('instrument', 'Unknown')}
Fire Radiative Power (FRP): {event.get('frp')} MW
Brightness Temperature: {event.get('brightness')} K
Detection Confidence: {confidence_label}
Data Source: {event.get('source', 'UNKNOWN')}

=== GEOGRAPHIC CONTEXT ===
Land Cover: {geo.get('land_cover', 'UNKNOWN')}
Search Radius: {geo.get('search_radius_km')} km
Nearby Industrial Facilities ({geo.get('facility_count', 0)} found):
{facilities_str}

=== HISTORICAL CONTEXT ===
{hist_str}

=== CLASSIFICATION ===
Type: {cls.get('type', 'UNKNOWN')}
Confidence: {cls.get('confidence', 0):.0%}
Primary Classification Factor: {cls.get('primary_factor', 'unknown')}
Classification Rules Fired:
  {rules_str}

=== RISK ASSESSMENT ===
Risk Level: {risk.get('level', 'UNKNOWN')}
Risk Score: {risk.get('score', 0):.1f}/100
Risk Components: {json.dumps(risk.get('components', {}), indent=None)}

=== INSTRUCTION ===
Analyse the above evidence and explain:
1. What is happening at this location
2. Why this classification and risk level were assigned
3. What makes this event notable or concerning (or not)
4. What an operator should investigate

Use ONLY the evidence above. Do not invent any additional facts."""


def _fallback_investigation(packet: dict[str, Any]) -> dict[str, Any]:
    """
    Generate a deterministic investigation from the packet without LLM.

    Clearly marked as AI_MODE=FALLBACK.
    """
    event = packet.get("event", {})
    geo = packet.get("geographic_context", {})
    hist = packet.get("historical_context", {})
    cls = packet.get("classification", {})
    risk = packet.get("risk", {})

    cls_type = cls.get("type", "UNKNOWN")
    risk_level = risk.get("level", "UNKNOWN")
    risk_score = risk.get("score", 0)
    frp = event.get("frp", 0)
    land_cover = geo.get("land_cover", "UNKNOWN")
    nearest_km = geo.get("nearest_facility_km")
    nearest = geo.get("nearest_facility")
    anomaly = hist.get("anomaly_ratio")
    persistence = hist.get("persistence_score", 0)

    # Build summary
    if cls_type == "INDUSTRIAL_THERMAL" and nearest:
        summary = (
            f"A {risk_level} risk industrial thermal signature ({frp} MW FRP) was detected "
            f"near {nearest.get('name', 'an industrial facility')} "
            f"({nearest_km:.2f} km away). "
            f"Land cover is {land_cover}."
        )
        situation = (
            f"Industrial thermal activity detected near a {nearest.get('type', 'facility')} "
            f"at {event.get('latitude')}, {event.get('longitude')}."
        )
    elif cls_type == "WILDFIRE":
        summary = (
            f"A {risk_level} risk wildfire signature ({frp} MW FRP) was detected "
            f"in {land_cover.lower()} terrain. "
            f"{'No industrial facilities within search radius.' if nearest is None else f'Nearest facility is {nearest_km:.1f} km away.'}"
        )
        situation = f"Potential wildfire in {land_cover.lower()} terrain at {event.get('latitude')}, {event.get('longitude')}."
    elif cls_type == "AGRICULTURAL_BURNING":
        summary = (
            f"A {risk_level} risk agricultural burning signature ({frp} MW FRP) was detected "
            f"in {land_cover.lower()} land. "
            f"This is consistent with seasonal crop burning."
        )
        situation = f"Agricultural burning in {land_cover.lower()} at {event.get('latitude')}, {event.get('longitude')}."
    else:
        summary = (
            f"A {risk_level} risk thermal event ({frp} MW FRP) was detected "
            f"and classified as {cls_type}. "
            f"Land cover: {land_cover}. Risk score: {risk_score:.1f}/100."
        )
        situation = f"Thermal event at {event.get('latitude')}, {event.get('longitude')} requires investigation."

    # Build reasoning list
    reasoning = []
    primary = cls.get("primary_factor", "")
    if primary and primary != "no_evidence":
        reasoning.append(f"Primary classification factor: {primary}")

    if nearest:
        reasoning.append(
            f"Nearest industrial facility is {nearest.get('name', 'Unknown')} "
            f"({nearest.get('type', 'UNKNOWN')}) at {nearest_km:.2f} km."
        )
    else:
        reasoning.append("No industrial facilities detected within the search radius.")

    if land_cover != "UNKNOWN":
        reasoning.append(f"Land cover classification is {land_cover}.")

    if hist.get("has_history"):
        baseline = hist.get("historical_baseline")
        if anomaly is not None:
            reasoning.append(
                f"Current FRP ({frp} MW) is {anomaly:.2f}x the historical baseline "
                f"({baseline:.1f} MW) — "
                + ("anomalous" if anomaly > 2 else "within normal range") + "."
            )
        if persistence > 0.2:
            reasoning.append(
                f"Persistent thermal activity at this location "
                f"(persistence score: {persistence:.2f})."
            )
    else:
        reasoning.append("No historical thermal activity recorded at this location (first detection).")

    rules = cls.get("rules_fired", [])
    if rules:
        reasoning.append(f"Classification rules triggered: {'; '.join(rules[:3])}.")

    return {
        "summary": summary,
        "situation": situation,
        "reasoning": reasoning,
        "assessment": (
            f"Backend classification: {cls_type} with {cls.get('confidence', 0):.0%} confidence. "
            f"Risk: {risk_level} ({risk_score:.1f}/100)."
        ),
        "recommended_action": _recommend_action(cls_type, risk_level, nearest, anomaly),
        "confidence_assessment": (
            "FALLBACK mode — deterministic explanation generated from backend evidence. "
            "No LLM was used. All facts are from the investigation packet."
        ),
        "ai_mode": "FALLBACK",
    }


def _recommend_action(
    cls_type: str,
    risk_level: str,
    nearest: dict | None,
    anomaly: float | None,
) -> str:
    """Generate a specific recommended action based on classification and risk."""
    if risk_level == "EXTREME":
        if cls_type == "INDUSTRIAL_THERMAL" and nearest:
            return (
                f"Immediately notify {nearest.get('name', 'the nearby facility')} "
                f"and dispatch field verification team to confirm industrial incident or equipment failure."
            )
        return "Initiate emergency response protocol. Dispatch field team immediately for ground verification."

    if risk_level == "HIGH":
        if cls_type == "WILDFIRE":
            return "Alert fire services and monitor for rapid spread. Verify with aerial imagery within 1 hour."
        if cls_type == "INDUSTRIAL_THERMAL":
            return (
                f"Contact {'nearby facility management' if nearest else 'local industrial authority'} "
                f"and schedule verification visit within 4 hours."
            )
        return "Assign for priority investigation. Obtain supplementary imagery within 4 hours."

    if risk_level == "MODERATE":
        if cls_type == "AGRICULTURAL_BURNING":
            return "Log event as probable agricultural burning. Flag for periodic monitoring if recurrence increases."
        return "Schedule routine investigation. Cross-reference with local authority records."

    return "Log and monitor. No immediate action required unless anomaly persists."


async def generate_investigation(
    packet: dict[str, Any],
    groq_api_key: str,
) -> dict[str, Any]:
    """
    Generate an AI investigation from the full evidence packet.

    Always returns a result — falls back to deterministic if Groq fails.

    Args:
        packet:       Complete investigation packet from build_investigation_packet().
        groq_api_key: Groq API key (may be empty string).

    Returns:
        Investigation dict with summary, reasoning, recommended_action, etc.
    """
    if not groq_api_key:
        logger.info("No Groq API key — using deterministic fallback for event %s",
                    packet.get("event", {}).get("id"))
        return _fallback_investigation(packet)

    try:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=groq_api_key)
        prompt = _build_investigation_prompt(packet)

        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,   # low temperature = more factual, less creative
            max_tokens=700,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        result = json.loads(content)

        # Validate required fields
        required = {"summary", "situation", "reasoning", "assessment",
                    "recommended_action", "confidence_assessment"}
        if not required.issubset(result.keys()):
            logger.warning("Groq response missing fields — falling back")
            return _fallback_investigation(packet)

        result["ai_mode"] = "GROQ"
        result["model"] = GROQ_MODEL

        logger.info(
            "Groq investigation generated for event %s",
            packet.get("event", {}).get("id"),
        )
        return result

    except Exception as exc:
        logger.error("Groq investigation failed: %s — using fallback", exc)
        return _fallback_investigation(packet)


# ── Legacy compatibility ──────────────────────────────────────────────────
# Keep the old generate_event_summary() for the existing ingest_service.py
# until we fully migrate it. This wraps the new generate_investigation().

async def generate_event_summary(
    groq_api_key: str,
    event_data: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Legacy single-event summary for HIGH/EXTREME events during ingestion.

    This is kept for backward compatibility with ingest_service.py.
    New code should use generate_investigation() with a full packet.
    """
    if not groq_api_key:
        return None

    try:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=groq_api_key)

        frp = event_data.get("frp")
        brightness = event_data.get("brightness")
        lat = event_data.get("latitude")
        lon = event_data.get("longitude")
        risk_level = event_data.get("risk_level", "HIGH")
        acq_date = event_data.get("acq_date", "unknown")
        acq_time = event_data.get("acq_time", "0000")
        daynight = "daytime" if event_data.get("daynight") == "D" else "nighttime"
        confidence = event_data.get("confidence", "unknown")
        satellite = event_data.get("satellite", "unknown")

        prompt = (
            f"Analyse this satellite-detected thermal event:\n\n"
            f"Location: {lat}°, {lon}°\n"
            f"Detection: {acq_date} {acq_time[:2]}:{acq_time[2:]} UTC ({daynight})\n"
            f"Satellite: {satellite} | Risk: {risk_level}\n"
            f"FRP: {frp} MW | Brightness: {brightness} K | Confidence: {confidence}\n\n"
            f"Generate a brief intelligence summary."
        )

        system = (
            "You are ThermaSense AI. Respond with valid JSON: "
            '{"summary":"...","key_threats":["..."],'
            '"recommended_action":"...","confidence_assessment":"..."}'
        )

        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=400,
            response_format={"type": "json_object"},
        )

        return json.loads(response.choices[0].message.content)

    except Exception as exc:
        logger.error("Legacy Groq summary failed: %s", exc)
        return None


def format_summary_text(groq_result: dict[str, Any] | None) -> str | None:
    """
    Convert Groq JSON result into a single formatted text block.
    Kept for backward compatibility with ingest_service.py.
    """
    if not groq_result:
        return None

    lines = []
    if s := groq_result.get("summary"):
        lines.append(s)
    if threats := groq_result.get("key_threats"):
        lines.append("Threats: " + (" | ".join(threats) if isinstance(threats, list) else str(threats)))
    if action := groq_result.get("recommended_action"):
        lines.append(f"Action: {action}")
    if assessment := groq_result.get("confidence_assessment"):
        lines.append(f"Confidence: {assessment}")

    return "\n".join(lines) if lines else None
