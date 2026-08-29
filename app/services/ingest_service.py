"""
Ingest orchestration service.

Ties together:
  1. FIRMS fetch   → firms_client.py
  2. CSV parsing   → ingestion/parser.py
  3. Classification → services/classifier.py
  4. DB upsert     → SQLAlchemy (upsert-on-conflict)
  5. Groq summaries → services/groq_analyst.py (HIGH + EXTREME only)
"""

import logging
from datetime import datetime, timezone

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import func, select, text
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
      fetch → parse → classify → upsert → groq-enrich

    Returns a summary dict for the API response.
    """
    settings = get_settings()
    start_time = datetime.now(timezone.utc)

    # ── 1. Fetch from NASA FIRMS ────────────────────────────────────
    try:
        raw_csv = await fetch_firms_csv(
            api_key=settings.firms_api_key,
            bbox=settings.demo_bbox,
            day_range=1,
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
    high_extreme_events: list[ThermalEvent] = []

    for event in parsed_events:
        risk_level, risk_score = classify(event)

        # Build PostGIS POINT geometry
        geom = from_shape(Point(event.longitude, event.latitude), srid=4326)

        # pg_insert with ON CONFLICT DO NOTHING (deduplication)
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
            )
            .on_conflict_do_nothing(
                constraint="uq_hotspot"
            )
            .returning(ThermalEvent.id, ThermalEvent.risk_level)
        )

        result = await db.execute(stmt)
        row = result.fetchone()

        if row:
            inserted += 1
            if risk_level in GROQ_TRIGGER_LEVELS:
                # Retrieve the full object for Groq enrichment
                te = await db.get(ThermalEvent, row[0])
                if te:
                    high_extreme_events.append(te)
        else:
            skipped += 1

    await db.flush()
    logger.info("Upserted %d new events, skipped %d duplicates", inserted, skipped)

    # ── 4. Groq enrichment (HIGH + EXTREME only) ────────────────────
    groq_count = 0
    groq_api_key = settings.groq_api_key

    # Limit Groq calls to top-5 highest FRP events to avoid rate limits
    top_events = sorted(
        high_extreme_events,
        key=lambda e: (e.frp or 0),
        reverse=True,
    )[:5]

    for te in top_events:
        if te.ai_generated:
            continue  # already has a summary

        groq_result = await generate_event_summary(
            groq_api_key=groq_api_key,
            event_data={
                "latitude": te.latitude,
                "longitude": te.longitude,
                "frp": te.frp,
                "brightness": te.brightness,
                "confidence": te.confidence,
                "satellite": te.satellite,
                "daynight": te.daynight,
                "acq_date": str(te.acq_date),
                "acq_time": te.acq_time,
                "risk_level": te.risk_level.value,
            },
        )

        if groq_result:
            te.ai_summary = format_summary_text(groq_result)
            te.ai_generated = True
            groq_count += 1

    await db.flush()

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

    return {
        "status": "ok",
        "fetched": fetched,
        "inserted": inserted,
        "skipped_duplicates": skipped,
        "groq_summaries_generated": groq_count,
        "message": (
            f"Ingested {inserted} new events ({skipped} duplicates skipped). "
            f"Generated {groq_count} AI summaries. Completed in {elapsed:.1f}s."
        ),
        "details": {
            "elapsed_seconds": elapsed,
            "groq_enriched_event_count": groq_count,
        },
    }


async def get_stats(db: AsyncSession) -> dict:
    """Compute summary stats for the /stats endpoint."""
    from datetime import timedelta

    # Total count
    total = await db.scalar(select(func.count(ThermalEvent.id)))

    # By risk level
    risk_rows = await db.execute(
        select(ThermalEvent.risk_level, func.count(ThermalEvent.id))
        .group_by(ThermalEvent.risk_level)
    )
    by_risk = {row[0].value: row[1] for row in risk_rows}

    # Last 24h
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    last_24h = await db.scalar(
        select(func.count(ThermalEvent.id)).where(ThermalEvent.created_at >= cutoff)
    )

    # Latest ingestion time
    last_created = await db.scalar(select(func.max(ThermalEvent.created_at)))

    return {
        "total_events": total or 0,
        "by_risk_level": by_risk,
        "last_ingestion": last_created,
        "events_last_24h": last_24h or 0,
        "extreme_count": by_risk.get("EXTREME", 0),
        "high_count": by_risk.get("HIGH", 0),
    }
