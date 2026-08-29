"""
Observation service — business logic orchestrator.

Coordinates the full ingestion pipeline:
  FIRMS fetch → normalize → validate → deduplicate → store

Also provides observation query methods that delegate
to the repository layer.
"""

import csv
import io
import logging
import uuid
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.thermal_observation import ThermalObservation
from app.repositories import observation_repository, ingestion_repository
from app.services import observation_normalizer
from app.services.firms_service import fetch_hotspots, SATELLITE_SOURCES

logger = logging.getLogger(__name__)


async def ingest_firms_data(
    session: AsyncSession,
    *,
    source: str,
    area: str = "world",
    day_range: int = 1,
) -> dict:
    """
    Full ingestion pipeline: fetch → normalize → validate → store.

    Args:
        session: Async database session.
        source: FIRMS source ID (e.g. VIIRS_NOAA20_NRT).
        area: Geographic area ('world' or bounding box).
        day_range: Number of past days (1-5).

    Returns:
        Ingestion summary dict.
    """
    settings = get_settings()

    # ── Create ingestion log ─────────────────────────────────────
    log = await ingestion_repository.create_ingestion_log(
        session,
        source=source,
        area=area,
        day_range=day_range,
    )
    await session.commit()

    try:
        # ── Step 1: Fetch raw data via Module 1 ──────────────────
        # Resolve source name to satellite for firms_service
        satellite_name = None
        for name, src_id in SATELLITE_SOURCES.items():
            if src_id == source:
                satellite_name = name
                break

        if satellite_name is None:
            # Try using the source directly
            satellite_name = source

        observations_list, source_used, area_used = await fetch_hotspots(
            map_key=settings.firms_map_key,
            satellite=satellite_name,
            day_range=day_range,
            area=area,
        )

        # We need raw CSV rows for the normalizer, but firms_service
        # already parses them. To get raw rows, we'll re-fetch the CSV
        # and use csv.DictReader. However, to avoid duplicate fetching,
        # let's convert HotspotResponse objects back to row dicts.
        raw_rows = []
        for obs in observations_list:
            raw_rows.append({
                "latitude": str(obs.latitude),
                "longitude": str(obs.longitude),
                "acq_date": obs.acquisition_datetime.strftime("%Y-%m-%d"),
                "acq_time": obs.acquisition_datetime.strftime("%H%M"),
                "satellite": obs.satellite,
                "instrument": obs.instrument,
                "brightness": str(obs.brightness) if obs.brightness is not None else "",
                "bright_ti4": str(obs.bright_ti4) if obs.bright_ti4 is not None else "",
                "bright_ti5": str(obs.bright_ti5) if obs.bright_ti5 is not None else "",
                "frp": str(obs.frp) if obs.frp is not None else "",
                "confidence": obs.confidence or "",
                "daynight": obs.daynight or "",
            })

        fetched_count = len(raw_rows)
        logger.info("Fetched %d raw observations from FIRMS", fetched_count)

        # ── Step 2: Normalize & validate ─────────────────────────
        valid_obs, errors = observation_normalizer.normalize_rows(
            raw_rows, source_used
        )

        invalid_count = len(errors)
        if errors:
            logger.warning(
                "Validation errors: %s",
                [f"Row {e.row_index}: {e.field} - {e.message}" for e in errors[:5]],
            )

        # ── Step 3: Prepare for bulk insert ──────────────────────
        observation_dicts = []
        for obs in valid_obs:
            observation_dicts.append({
                "id": uuid.uuid4(),
                "source": obs.source,
                "latitude": obs.latitude,
                "longitude": obs.longitude,
                "acquisition_datetime": obs.acquisition_datetime,
                "acq_date": obs.acq_date,
                "acq_time": obs.acq_time,
                "satellite": obs.satellite,
                "instrument": obs.instrument,
                "brightness": obs.brightness,
                "bright_ti4": obs.bright_ti4,
                "bright_ti5": obs.bright_ti5,
                "frp": obs.frp,
                "confidence": obs.confidence,
                "daynight": obs.daynight,
                "raw_data": obs.raw_data,
                "observation_hash": obs.observation_hash,
            })

        # ── Step 4: Bulk insert with duplicate skipping ──────────
        stored, duplicates = await observation_repository.bulk_create_observations(
            session, observation_dicts
        )

        # ── Step 5: Update ingestion log ─────────────────────────
        await ingestion_repository.update_ingestion_log(
            session,
            log.id,
            status="success",
            records_fetched=fetched_count,
            records_stored=stored,
            duplicates_skipped=duplicates,
            invalid_records=invalid_count,
        )
        await session.commit()

        summary = {
            "source": source_used,
            "fetched": fetched_count,
            "validated": len(valid_obs),
            "stored": stored,
            "duplicates": duplicates,
            "invalid": invalid_count,
            "status": "success",
        }
        logger.info("Ingestion complete: %s", summary)
        return summary

    except Exception as exc:
        # Update log with error
        await ingestion_repository.update_ingestion_log(
            session,
            log.id,
            status="error",
            error_message=str(exc)[:1000],
        )
        await session.commit()
        raise


async def get_observation(
    session: AsyncSession,
    observation_id: uuid.UUID,
) -> Optional[ThermalObservation]:
    """Retrieve a single stored observation by UUID."""
    return await observation_repository.get_observation_by_id(
        session, observation_id
    )


async def list_observations(
    session: AsyncSession,
    *,
    source: Optional[str] = None,
    satellite: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    min_lat: Optional[float] = None,
    min_lon: Optional[float] = None,
    max_lat: Optional[float] = None,
    max_lon: Optional[float] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[ThermalObservation], int]:
    """Paginated, filterable observation listing."""
    return await observation_repository.list_observations(
        session,
        source=source,
        satellite=satellite,
        start_date=start_date,
        end_date=end_date,
        min_lat=min_lat,
        min_lon=min_lon,
        max_lat=max_lat,
        max_lon=max_lon,
        limit=limit,
        offset=offset,
    )
