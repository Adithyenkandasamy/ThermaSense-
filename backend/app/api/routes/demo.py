"""Demo data routes."""

import logging
from datetime import date, datetime, time, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from geoalchemy2.shape import from_shape
from pydantic import BaseModel, Field
from shapely.geometry import Point
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.thermal_event import RiskLevel, ThermalEvent
from app.services.analysis_service import process_event
from app.services.connection_manager import manager as ws_manager
from app.services.demo_data_service import seed_demo_data

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

# ── Scenario presets ────────────────────────────────────────────────────────
# Each preset chooses coordinates that give the classification engine
# the best chance of producing the intended result with the existing
# facilities that are already in the DB from sync_facilities_on_startup.

_SCENARIO_PRESETS: dict[str, dict] = {
    "industrial": {
        # Near Example Refinery (12.3499, 78.9068) — guaranteed BUILT_UP context
        "latitude": 12.348,
        "longitude": 78.905,
        "frp": 185.0,
        "brightness": 342.0,
        "confidence": "high",
        "label": "Industrial Thermal (near refinery)",
    },
    "wildfire": {
        # Remote location away from all demo facilities — heuristic gives FOREST
        "latitude": 12.900,
        "longitude": 79.450,
        "frp": 320.0,
        "brightness": 385.0,
        "confidence": "high",
        "label": "Wildfire (remote, high FRP)",
    },
    "agricultural": {
        # Open cropland location away from industrial facilities
        "latitude": 12.050,
        "longitude": 78.500,
        "frp": 35.0,
        "brightness": 318.0,
        "confidence": "nominal",
        "label": "Agricultural Burning (low FRP, open land)",
    },
    "mining": {
        # Near Eastern Quarry Complex (12.66, 78.61)
        "latitude": 12.655,
        "longitude": 78.615,
        "frp": 60.0,
        "brightness": 330.0,
        "confidence": "nominal",
        "label": "Mining Activity (near quarry)",
    },
    "persistent": {
        # Near the power plant (12.361, 78.886) — persistent industrial signature
        "latitude": 12.363,
        "longitude": 78.884,
        "frp": 95.0,
        "brightness": 335.0,
        "confidence": "nominal",
        "label": "Persistent Industrial (near power plant)",
    },
    "extreme": {
        # Near refinery, very high FRP — should score EXTREME
        "latitude": 12.347,
        "longitude": 78.908,
        "frp": 620.0,
        "brightness": 512.0,
        "confidence": "high",
        "label": "Extreme Industrial Event",
    },
}


class SimulateRequest(BaseModel):
    scenario: Literal["industrial", "wildfire", "agricultural", "mining", "persistent", "extreme"] = "industrial"
    latitude:   float | None = Field(None, ge=-90, le=90)
    longitude:  float | None = Field(None, ge=-180, le=180)
    frp:        float | None = Field(None, ge=0, le=10000)
    brightness: float | None = Field(None, ge=200, le=600)
    confidence: str | None   = None


@router.post("/simulate")
async def simulate_event(
    req: SimulateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Create a synthetic ThermalEvent and run the complete analysis pipeline.

    The event is clearly marked source='DEMO' and raw_data.simulated=true.
    It uses the SAME process_event() pipeline as real FIRMS data.
    """
    preset = _SCENARIO_PRESETS.get(req.scenario, _SCENARIO_PRESETS["industrial"])

    # Override with caller values where provided
    lat  = req.latitude   if req.latitude   is not None else preset["latitude"]
    lon  = req.longitude  if req.longitude  is not None else preset["longitude"]
    frp  = req.frp        if req.frp        is not None else preset["frp"]
    brgt = req.brightness if req.brightness is not None else preset["brightness"]
    conf = req.confidence if req.confidence is not None else preset["confidence"]

    now = datetime.now(timezone.utc)
    acq_date = now.date()
    acq_time = now.strftime("%H%M")
    geom = from_shape(Point(lon, lat), srid=4326)

    # Build a unique external_id so repeated simulations don't conflict
    ext_id = f"SIM-{req.scenario.upper()}-{now.strftime('%Y%m%d%H%M%S')}"

    # ── Insert ThermalEvent ────────────────────────────────────────────────
    stmt = (
        pg_insert(ThermalEvent)
        .values(
            external_id=ext_id,
            source="DEMO",
            geom=geom,
            latitude=lat,
            longitude=lon,
            acq_date=acq_date,
            acq_time=acq_time,
            observed_at=now,
            brightness=brgt,
            frp=frp,
            confidence=str(conf),
            satellite="DEMO-SAT",
            instrument="VIIRS",
            daynight="D",
            day_night="D",
            risk_level=RiskLevel.LOW,
            risk_score=0.0,
            raw_data={
                "demo": True,
                "simulated": True,
                "scenario": req.scenario,
                "label": preset["label"],
                "source": "POST /api/v1/demo/simulate",
            },
            ai_generated=False,
        )
        .on_conflict_do_nothing(constraint="uq_hotspot")
        .returning(ThermalEvent.id)
    )

    result = await db.execute(stmt)
    row = result.fetchone()

    if row is None:
        # Extremely rare: same lat/lon/date/time already exists — just fetch it
        from sqlalchemy import select
        existing = await db.execute(
            select(ThermalEvent).where(
                ThermalEvent.latitude == lat,
                ThermalEvent.longitude == lon,
                ThermalEvent.acq_date == acq_date,
                ThermalEvent.acq_time == acq_time,
            )
        )
        ev = existing.scalar_one_or_none()
        event_id = ev.id if ev else None
    else:
        event_id = row[0]

    if event_id is None:
        raise HTTPException(status_code=500, detail="Failed to create simulated event")

    await db.flush()

    # ── Run the full analysis pipeline ────────────────────────────────────
    try:
        analysis_result = await process_event(event_id, db)
    except Exception as exc:
        logger.error("process_event failed for simulated event %s: %s", event_id, exc)
        raise HTTPException(status_code=500, detail=f"Analysis pipeline failed: {exc}")

    await db.commit()

    # ── Broadcast THERMAL_EVENT_ANALYZED ─────────────────────────────────
    risk_level_str = analysis_result.get("risk_level", "LOW")
    risk_score_val = analysis_result.get("risk_score", 0.0)
    classification_str = analysis_result.get("classification", "UNKNOWN")

    await ws_manager.broadcast({
        "type": "THERMAL_EVENT_ANALYZED",
        "event_id": event_id,
        "classification": classification_str,
        "risk_level": risk_level_str,
        "risk_score": risk_score_val,
        "latitude": lat,
        "longitude": lon,
        "frp": frp,
        "scenario": req.scenario,
        "simulated": True,
    })

    # ── Broadcast THERMAL_ALERT for HIGH / EXTREME ─────────────────────
    if risk_level_str in ("HIGH", "EXTREME"):
        investigation = analysis_result.get("investigation", {})
        await ws_manager.broadcast({
            "type": "THERMAL_ALERT",
            "event_id": event_id,
            "risk_level": risk_level_str,
            "risk_score": risk_score_val,
            "classification": classification_str,
            "latitude": lat,
            "longitude": lon,
            "timestamp": now.isoformat(),
            "summary": investigation.get("summary", "High-risk thermal event detected."),
            "simulated": True,
        })
        logger.info(
            "THERMAL_ALERT broadcast for simulated event %s (risk=%s score=%.1f)",
            event_id, risk_level_str, risk_score_val,
        )

    return {
        "status": "ok",
        "event_id": event_id,
        "scenario": req.scenario,
        "label": preset["label"],
        "simulated": True,
        "source": "DEMO",
        "location": {"latitude": lat, "longitude": lon},
        "thermal": {"frp": frp, "brightness": brgt, "confidence": conf},
        "classification": classification_str,
        "risk_level": risk_level_str,
        "risk_score": risk_score_val,
        "analysis_id": analysis_result.get("analysis_id"),
        "ai_mode": analysis_result.get("investigation", {}).get("ai_mode", "FALLBACK"),
        "alert_broadcast": risk_level_str in ("HIGH", "EXTREME"),
        "message": (
            f"Simulated {req.scenario} event created and analyzed. "
            f"Classification: {classification_str}, Risk: {risk_level_str} ({risk_score_val:.1f})."
        ),
    }


@router.post("/seed")
async def seed_demo(db: AsyncSession = Depends(get_db)) -> dict:
    result = await seed_demo_data(db)
    await db.commit()
    return result
