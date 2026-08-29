"""
Central event analysis orchestration.

process_event(event_id, db) is the SINGLE source of truth for
running the complete analysis pipeline on one thermal event:

    load event
        ↓
    build_event_context()     — PostGIS nearby facilities + land cover
        ↓
    calculate_history()       — real DB historical queries
        ↓
    classify_event()          — rule-based classification
        ↓
    calculate_risk()          — extended risk engine
        ↓
    build_investigation_packet()
        ↓
    generate_investigation()  — Groq AI or deterministic fallback
        ↓
    store EventAnalysis        — upsert into event_analysis table

Design:
  - If analysis fails at any step, the ThermalEvent is preserved.
    Only the EventAnalysis creation fails — this is logged and
    can be retried by calling process_event() again or via POST /analyze.
  - process_event() is idempotent — re-running it updates the analysis.
  - The DB session must be provided by the caller (route or worker).
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.thermal_event import EventAnalysis, ThermalEvent
from app.services.classification_engine import classify_event
from app.services.context_service import build_event_context
from app.services.groq_analyst import generate_investigation
from app.services.history_service import calculate_history
from app.services.investigation_packet import build_investigation_packet
from app.services.risk_engine import calculate_risk

logger = logging.getLogger(__name__)

ENGINE_VERSION = "v2.0-context-aware"


async def process_event(
    event_id: int,
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Run the complete analysis pipeline for one thermal event.

    Args:
        event_id: Primary key of the ThermalEvent to analyse.
        db:       Async SQLAlchemy session (caller manages commit).

    Returns:
        Complete analysis result dict including packet + investigation.

    Raises:
        ValueError: if the event is not found.
        Exception:  if a critical step fails (event data itself is preserved).
    """
    settings = get_settings()

    # ── 1. Load event ──────────────────────────────────────────────────────
    event: ThermalEvent | None = await db.get(ThermalEvent, event_id)
    if event is None:
        raise ValueError(f"Event {event_id} not found")

    logger.info("Starting analysis for event %s (lat=%s lon=%s frp=%s)",
                event.id, event.latitude, event.longitude, event.frp)

    # ── 2. Build geospatial context ────────────────────────────────────────
    try:
        context = await build_event_context(event, db)
    except Exception as exc:
        logger.error("Context build failed for event %s: %s", event_id, exc)
        context = {
            "event_id": event_id,
            "location": {"latitude": event.latitude, "longitude": event.longitude},
            "nearby_facilities": [],
            "nearest_facility": None,
            "nearest_facility_km": None,
            "land_cover": "UNKNOWN",
            "radius_km": 10.0,
        }

    # ── 3. Historical analysis ─────────────────────────────────────────────
    try:
        history = await calculate_history(event, db)
    except Exception as exc:
        logger.error("History calculation failed for event %s: %s", event_id, exc)
        history = {
            "event_id": event_id,
            "radius_km": 1.0,
            "detections_7d": 0,
            "detections_30d": 0,
            "detections_90d": 0,
            "active_days": 0,
            "average_frp": None,
            "maximum_frp": event.frp,
            "historical_baseline": None,
            "current_frp": event.frp or 0.0,
            "anomaly_ratio": None,
            "persistence_score": 0.0,
            "has_history": False,
        }

    # ── 4. Classification ──────────────────────────────────────────────────
    try:
        classification_result = classify_event(event, context, history)
    except Exception as exc:
        logger.error("Classification failed for event %s: %s", event_id, exc)
        from app.models.thermal_event import EventClassification
        classification_result = {
            "classification": EventClassification.UNKNOWN,
            "confidence": 0.0,
            "evidence": {"rules_fired": [], "primary_factor": "classification_error"},
        }

    # ── 5. Risk assessment ─────────────────────────────────────────────────
    try:
        risk_result = calculate_risk(event, context, history, classification_result)
    except Exception as exc:
        logger.error("Risk calculation failed for event %s: %s", event_id, exc)
        risk_result = {
            "risk_score": event.risk_score,
            "risk_level": event.risk_level,
            "components": {},
        }

    # ── 6. Build investigation packet ─────────────────────────────────────
    packet = build_investigation_packet(
        event=event,
        context=context,
        history=history,
        classification_result=classification_result,
        risk_result=risk_result,
    )

    # ── 7. AI investigation ────────────────────────────────────────────────
    try:
        investigation = await generate_investigation(
            packet=packet,
            groq_api_key=settings.groq_api_key,
        )
    except Exception as exc:
        logger.error("AI investigation failed for event %s: %s", event_id, exc)
        from app.services.groq_analyst import _fallback_investigation
        investigation = _fallback_investigation(packet)

    # ── 8. Store EventAnalysis ─────────────────────────────────────────────
    classification_val = classification_result.get("classification")
    risk_level_val = risk_result.get("risk_level")
    risk_score_val = risk_result.get("risk_score", 0.0)
    anomaly_score = history.get("anomaly_ratio") or 0.0

    # Cap anomaly_score to 0–1 range for the DB column
    anomaly_score_capped = min(anomaly_score / 10.0, 1.0) if anomaly_score > 0 else 0.0

    # Build the reasoning text (join AI reasoning list if available)
    ai_reasoning = investigation.get("reasoning", [])
    reasoning_text = (
        "\n".join(ai_reasoning)
        if isinstance(ai_reasoning, list)
        else str(ai_reasoning)
    )

    # Build evidence JSON for the DB record
    evidence_json = {
        "packet": packet,
        "ai_result": investigation,
        "classification_evidence": classification_result.get("evidence", {}),
        "risk_components": risk_result.get("components", {}),
    }

    try:
        stmt = (
            pg_insert(EventAnalysis)
            .values(
                event_id=event_id,
                classification=classification_val,
                confidence=classification_result.get("confidence", 0.0),
                risk_score=risk_score_val,
                risk_level=risk_level_val,
                persistence_score=history.get("persistence_score", 0.0),
                anomaly_score=anomaly_score_capped,
                industrial_context_score=(
                    1.0 if context.get("nearest_facility_km") is not None
                    and context["nearest_facility_km"] <= 2.0
                    else (
                        0.5 if context.get("nearest_facility_km") is not None
                        else 0.0
                    )
                ),
                summary=investigation.get("summary", "Analysis complete."),
                reasoning=reasoning_text,
                recommended_action=investigation.get(
                    "recommended_action", "Review event and nearby context."
                ),
                evidence=evidence_json,
                engine_version=ENGINE_VERSION,
            )
            .on_conflict_do_update(
                constraint="uq_event_analysis_event_id",
                set_={
                    "classification": classification_val,
                    "confidence": classification_result.get("confidence", 0.0),
                    "risk_score": risk_score_val,
                    "risk_level": risk_level_val,
                    "persistence_score": history.get("persistence_score", 0.0),
                    "anomaly_score": anomaly_score_capped,
                    "industrial_context_score": (
                        1.0 if context.get("nearest_facility_km") is not None
                        and context["nearest_facility_km"] <= 2.0
                        else (
                            0.5 if context.get("nearest_facility_km") is not None
                            else 0.0
                        )
                    ),
                    "summary": investigation.get("summary", "Analysis complete."),
                    "reasoning": reasoning_text,
                    "recommended_action": investigation.get(
                        "recommended_action", "Review event and nearby context."
                    ),
                    "evidence": evidence_json,
                    "engine_version": ENGINE_VERSION,
                },
            )
            .returning(EventAnalysis.id)
        )

        result = await db.execute(stmt)
        analysis_id = result.scalar_one()
        await db.flush()

        logger.info(
            "EventAnalysis %s stored for event %s "
            "(classification=%s risk=%s score=%.1f ai_mode=%s)",
            analysis_id,
            event_id,
            classification_val.value if hasattr(classification_val, "value") else classification_val,
            risk_level_val.value if hasattr(risk_level_val, "value") else risk_level_val,
            risk_score_val,
            investigation.get("ai_mode", "unknown"),
        )

        # Also update risk on the ThermalEvent itself for the list endpoints
        event.risk_score = risk_score_val
        event.risk_level = risk_level_val
        await db.flush()

    except Exception as exc:
        logger.error("Failed to store EventAnalysis for event %s: %s", event_id, exc)
        # Re-raise so caller knows analysis storage failed.
        # The ThermalEvent itself was already committed before this call.
        raise

    return {
        "event_id": event_id,
        "analysis_id": analysis_id,
        "packet": packet,
        "investigation": investigation,
        "classification": (
            classification_val.value
            if hasattr(classification_val, "value")
            else str(classification_val)
        ),
        "risk_level": (
            risk_level_val.value
            if hasattr(risk_level_val, "value")
            else str(risk_level_val)
        ),
        "risk_score": risk_score_val,
    }


async def get_analysis_for_event(
    event_id: int, db: AsyncSession
) -> EventAnalysis | None:
    """
    Retrieve the stored EventAnalysis for an event (if it exists).
    """
    result = await db.execute(
        select(EventAnalysis).where(EventAnalysis.event_id == event_id)
    )
    return result.scalar_one_or_none()


async def get_stats(db: AsyncSession) -> dict:
    """Compute summary stats for the /stats endpoint."""
    from datetime import timedelta, timezone
    from datetime import datetime as dt

    from sqlalchemy import func

    total = await db.scalar(select(func.count(ThermalEvent.id)))
    risk_rows = await db.execute(
        select(ThermalEvent.risk_level, func.count(ThermalEvent.id))
        .group_by(ThermalEvent.risk_level)
    )
    by_risk = {row[0].value: row[1] for row in risk_rows}
    cutoff = dt.now(timezone.utc) - timedelta(hours=24)
    last_24h = await db.scalar(
        select(func.count(ThermalEvent.id)).where(ThermalEvent.created_at >= cutoff)
    )
    last_created = await db.scalar(select(func.max(ThermalEvent.created_at)))

    return {
        "total_events": total or 0,
        "by_risk_level": by_risk,
        "last_ingestion": last_created,
        "events_last_24h": last_24h or 0,
        "extreme_count": by_risk.get("EXTREME", 0),
        "high_count": by_risk.get("HIGH", 0),
    }
