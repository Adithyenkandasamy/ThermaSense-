"""
Ingest orchestration service.

Pipeline:
  1. FIRMS fetch      → ingestion/firms_client.py
  2. CSV parsing      → ingestion/parser.py
  3. Risk classify    → services/classifier.py  (fast, at insert time)
  4. DB upsert        → ON CONFLICT DO NOTHING
  5. Full analysis    → services/analysis_service.process_event()
                          ├── context (PostGIS facilities + land cover)
                          ├── history (real DB queries)
                          ├── classification (rule-based engine)
                          ├── risk (extended engine)
                          ├── Groq AI (or fallback)
                          └── EventAnalysis stored
  6. WebSocket        → broadcast to connected clients

If analysis fails for a new event, the ThermalEvent is preserved.
Analysis can be retried via POST /api/v1/events/{id}/analyze.
"""

import logging
from datetime import datetime, timezone

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.ingestion.firms_client import fetch_firms_csv
from app.ingestion.parser import parse_firms_csv
from app.models.thermal_event import RiskLevel, ThermalEvent
from app.services.classifier import classify
from app.services.groq_analyst import (
    GROQ_TRIGGER_LEVELS,
    format_summary_text,
    generate_event_summary,
)

logger = logging.getLogger(__name__)


async def run_ingestion(db: AsyncSession) -> dict:
    """
    Full ingestion pipeline:
      fetch → parse → classify → upsert → full analysis → broadcast

    Returns a summary dict for the API response.
    """
    settings = get_settings()
    start_time = datetime.now(timezone.utc)

    if not settings.firms_api_key:
        from app.services.demo_data_service import seed_demo_data

        demo_result = await seed_demo_data(db)
        return {
            "status": "ok",
            "fetched": demo_result["events_inserted"],
            "inserted": demo_result["events_inserted"],
            "skipped_duplicates": 0,
            "groq_summaries_generated": 0,
            "message": "FIRMS_MAP_KEY is not configured — deterministic demo data seeded.",
            "details": demo_result,
        }

    # ── 1. Fetch from NASA FIRMS ────────────────────────────────────
    try:
        raw_csv = await fetch_firms_csv(
            api_key=settings.firms_api_key,
            bbox=settings.demo_bbox,
            day_range=1,
            source=settings.firms_source,
        )
    except Exception as exc:
        logger.error("FIRMS fetch failed: %s", exc)
        return {
            "status": "error",
            "fetched": 0,
            "inserted": 0,
            "skipped_duplicates": 0,
            "groq_summaries_generated": 0,
            "message": f"FIRMS fetch failed: {exc}",
        }

    # ── 2. Parse CSV ────────────────────────────────────────────────
    parsed_events = parse_firms_csv(raw_csv)
    fetched = len(parsed_events)
    logger.info("Parsed %d events from FIRMS", fetched)

    if fetched == 0:
        return {
            "status": "ok",
            "fetched": 0,
            "inserted": 0,
            "skipped_duplicates": 0,
            "groq_summaries_generated": 0,
            "message": "No events returned from FIRMS for this region/timeframe.",
        }

    # ── 3. Classify + upsert ────────────────────────────────────────
    inserted = 0
    skipped = 0
    new_event_ids: list[int] = []

    for event in parsed_events:
        risk_level, risk_score = classify(event)
        geom = from_shape(Point(event.longitude, event.latitude), srid=4326)

        stmt = (
            pg_insert(ThermalEvent)
            .values(
                geom=geom,
                latitude=event.latitude,
                longitude=event.longitude,
                acq_date=event.acq_date,
                acq_time=event.acq_time,
                brightness=event.brightness,
                frp=event.frp,
                confidence=event.confidence,
                satellite=event.satellite,
                instrument=event.instrument,
                daynight=event.daynight,
                scan=event.scan,
                track=event.track,
                version=event.version,
                risk_level=risk_level,
                risk_score=risk_score,
                source="VIIRS_SNPP_NRT",
            )
            .on_conflict_do_nothing(constraint="uq_hotspot")
            .returning(ThermalEvent.id, ThermalEvent.risk_level)
        )

        result = await db.execute(stmt)
        row = result.fetchone()

        if row:
            inserted += 1
            new_event_ids.append(row[0])
        else:
            skipped += 1

    await db.flush()
    logger.info("Upserted %d new events, skipped %d duplicates", inserted, skipped)

    # ── 4. Full analysis pipeline for each new event ──────────────────
    # We run analysis synchronously here so the ingest response reflects
    # the complete state. For high-volume production a task queue would
    # be used, but for the hackathon this is acceptable.
    analyzed = 0
    analysis_errors = 0
    websocket_broadcasts = 0

    if new_event_ids:
        from app.services.analysis_service import process_event
        from app.services.connection_manager import manager as ws_manager

        for event_id in new_event_ids:
            try:
                result = await process_event(event_id, db)
                analyzed += 1

                # ── 5. WebSocket broadcast ─────────────────────────────────
                if ws_manager.connection_count > 0:
                    await ws_manager.broadcast(
                        {
                            "type": "THERMAL_EVENT_ANALYZED",
                            "event_id": event_id,
                            "classification": result.get("classification", "UNKNOWN"),
                            "risk_level": result.get("risk_level", "UNKNOWN"),
                            "risk_score": result.get("risk_score", 0.0),
                            "latitude": result["packet"]["event"]["latitude"],
                            "longitude": result["packet"]["event"]["longitude"],
                            "frp": result["packet"]["event"]["frp"],
                        }
                    )
                    websocket_broadcasts += 1

            except Exception as exc:
                analysis_errors += 1
                logger.error(
                    "Analysis failed for new event %s: %s "
                    "(event data preserved, retry with POST /analyze)",
                    event_id,
                    exc,
                )

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

    return {
        "status": "ok",
        "fetched": fetched,
        "inserted": inserted,
        "skipped_duplicates": skipped,
        "analyzed": analyzed,
        "analysis_errors": analysis_errors,
        "groq_summaries_generated": analyzed,
        "websocket_broadcasts": websocket_broadcasts,
        "message": (
            f"Ingested {inserted} new events ({skipped} duplicates skipped). "
            f"Analysed {analyzed} events ({analysis_errors} errors). "
            f"Completed in {elapsed:.1f}s."
        ),
        "details": {"elapsed_seconds": elapsed},
    }


async def get_stats(db: AsyncSession) -> dict:
    """Compute summary stats — delegated to analysis_service to avoid duplication."""
    from app.services.analysis_service import get_stats as _get_stats
    return await _get_stats(db)
