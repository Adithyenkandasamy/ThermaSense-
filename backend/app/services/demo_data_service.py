"""Deterministic demo data for hackathon verification."""

from datetime import date, datetime, time, timezone

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.thermal_event import (
    EventAnalysis,
    EventClassification,
    IndustrialFacility,
    RiskLevel,
    ThermalEvent,
)


DEMO_EVENTS = [
    {
        "external_id": "DEMO-INDUSTRIAL-001",
        "latitude": 12.3456,
        "longitude": 78.9012,
        "acq_date": date(2026, 8, 29),
        "acq_time": "1030",
        "brightness": 342.0,
        "frp": 185.0,
        "confidence": "89",
        "risk_level": RiskLevel.HIGH,
        "risk_score": 86.0,
        "classification": EventClassification.INDUSTRIAL_THERMAL,
        "summary": "Likely industrial thermal activity near refinery infrastructure.",
    },
    {
        "external_id": "DEMO-PERSISTENT-002",
        "latitude": 12.352,
        "longitude": 78.892,
        "acq_date": date(2026, 8, 29),
        "acq_time": "1045",
        "brightness": 331.0,
        "frp": 92.0,
        "confidence": "nominal",
        "risk_level": RiskLevel.MODERATE,
        "risk_score": 58.0,
        "classification": EventClassification.INDUSTRIAL_THERMAL,
        "summary": "Persistent moderate thermal activity near industrial infrastructure.",
    },
    {
        "external_id": "DEMO-WILDFIRE-003",
        "latitude": 12.58,
        "longitude": 79.08,
        "acq_date": date(2026, 8, 29),
        "acq_time": "1110",
        "brightness": 368.0,
        "frp": 240.0,
        "confidence": "high",
        "risk_level": RiskLevel.HIGH,
        "risk_score": 82.0,
        "classification": EventClassification.WILDFIRE,
        "summary": "Potential wildfire thermal activity away from industrial facilities.",
    },
    {
        "external_id": "DEMO-AGRI-004",
        "latitude": 12.18,
        "longitude": 78.73,
        "acq_date": date(2026, 8, 29),
        "acq_time": "1135",
        "brightness": 318.0,
        "frp": 38.0,
        "confidence": "nominal",
        "risk_level": RiskLevel.MODERATE,
        "risk_score": 44.0,
        "classification": EventClassification.AGRICULTURAL_BURNING,
        "summary": "Potential agricultural burning pattern in open land context.",
    },
    {
        "external_id": "DEMO-UNKNOWN-005",
        "latitude": 12.72,
        "longitude": 78.55,
        "acq_date": date(2026, 8, 29),
        "acq_time": "1205",
        "brightness": 309.0,
        "frp": 8.0,
        "confidence": "low",
        "risk_level": RiskLevel.LOW,
        "risk_score": 19.0,
        "classification": EventClassification.UNKNOWN,
        "summary": "Low-confidence thermal anomaly with insufficient contextual evidence.",
    },
    {
        "external_id": "DEMO-EXTREME-006",
        "latitude": 12.337,
        "longitude": 78.918,
        "acq_date": date(2026, 8, 29),
        "acq_time": "1220",
        "brightness": 512.0,
        "frp": 610.0,
        "confidence": "high",
        "risk_level": RiskLevel.EXTREME,
        "risk_score": 96.0,
        "classification": EventClassification.INDUSTRIAL_THERMAL,
        "summary": "Abnormally high thermal event near multiple industrial facilities.",
    },
]

DEMO_FACILITIES = [
    {
        "external_id": "DEMO-FAC-REFINERY-001",
        "name": "Example Refinery",
        "facility_type": "REFINERY",
        "latitude": 12.3499,
        "longitude": 78.9068,
    },
    {
        "external_id": "DEMO-FAC-POWER-002",
        "name": "North Thermal Power Plant",
        "facility_type": "POWER_PLANT",
        "latitude": 12.361,
        "longitude": 78.886,
    },
    {
        "external_id": "DEMO-FAC-MINE-003",
        "name": "Eastern Quarry Complex",
        "facility_type": "MINE",
        "latitude": 12.66,
        "longitude": 78.61,
    },
]


async def seed_demo_data(db: AsyncSession) -> dict:
    facilities_inserted = 0
    events_inserted = 0
    analyses_inserted = 0

    for facility in DEMO_FACILITIES:
        geom = from_shape(Point(facility["longitude"], facility["latitude"]), srid=4326)
        stmt = (
            pg_insert(IndustrialFacility)
            .values(**facility, geom=geom, source="DEMO", facility_metadata={"demo": True})
            .on_conflict_do_nothing(constraint="uq_industrial_facilities_external_id")
            .returning(IndustrialFacility.id)
        )
        if (await db.execute(stmt)).fetchone():
            facilities_inserted += 1

    for demo in DEMO_EVENTS:
        observed_at = datetime.combine(
            demo["acq_date"],
            time(int(demo["acq_time"][:2]), int(demo["acq_time"][2:])),
            tzinfo=timezone.utc,
        )
        geom = from_shape(Point(demo["longitude"], demo["latitude"]), srid=4326)
        event_values = {
            key: demo[key]
            for key in (
                "external_id",
                "latitude",
                "longitude",
                "acq_date",
                "acq_time",
                "brightness",
                "frp",
                "confidence",
                "risk_level",
                "risk_score",
            )
        }
        event_values.update(
            {
                "geom": geom,
                "source": "DEMO",
                "observed_at": observed_at,
                "satellite": "DEMO-SAT",
                "instrument": "VIIRS",
                "daynight": "D",
                "day_night": "D",
                "raw_data": {"demo": True, "source": "deterministic seed"},
                "ai_summary": demo["summary"],
                "ai_generated": False,
            }
        )
        stmt = (
            pg_insert(ThermalEvent)
            .values(**event_values)
            .on_conflict_do_nothing(constraint="uq_hotspot")
            .returning(ThermalEvent.id)
        )
        row = (await db.execute(stmt)).fetchone()
        if row:
            events_inserted += 1

    event_rows = await db.execute(select(ThermalEvent).where(ThermalEvent.source == "DEMO"))
    for event in event_rows.scalars().all():
        demo = next((item for item in DEMO_EVENTS if item["external_id"] == event.external_id), None)
        if demo is None:
            continue
        stmt = (
            pg_insert(EventAnalysis)
            .values(
                event_id=event.id,
                classification=demo["classification"],
                confidence=0.89 if event.risk_level in {RiskLevel.HIGH, RiskLevel.EXTREME} else 0.68,
                risk_score=event.risk_score,
                risk_level=event.risk_level,
                persistence_score=0.72 if demo["classification"] == EventClassification.INDUSTRIAL_THERMAL else 0.32,
                anomaly_score=min((event.frp or 0) / 6.5, 100),
                industrial_context_score=0.9
                if demo["classification"] == EventClassification.INDUSTRIAL_THERMAL
                else 0.1,
                summary=demo["summary"],
                reasoning=(
                    "Demo evidence packet: facility proximity, land-cover label, historical baseline, "
                    "current FRP, anomaly ratio, and deterministic risk score."
                ),
                recommended_action="Investigate the location and validate nearby context with field or open-source evidence.",
                evidence={
                    "demo": True,
                    "land_cover": "BUILT_UP"
                    if demo["classification"] == EventClassification.INDUSTRIAL_THERMAL
                    else "OPEN_LAND",
                    "current_frp": event.frp,
                    "historical_average_frp": 42 if event.frp and event.frp > 100 else 18,
                    "anomaly_ratio": round((event.frp or 0) / (42 if event.frp and event.frp > 100 else 18), 2),
                    "nearby_facilities": [
                        {"name": "Example Refinery", "type": "REFINERY", "distance_km": 0.7}
                    ]
                    if demo["classification"] == EventClassification.INDUSTRIAL_THERMAL
                    else [],
                },
                engine_version="demo-v1",
            )
            .on_conflict_do_nothing(constraint="uq_event_analysis_event_id")
            .returning(EventAnalysis.id)
        )
        if (await db.execute(stmt)).fetchone():
            analyses_inserted += 1

    await db.flush()
    return {
        "status": "ok",
        "demo": True,
        "facilities_inserted": facilities_inserted,
        "events_inserted": events_inserted,
        "analyses_inserted": analyses_inserted,
        "message": "Deterministic ThermaSense demo data is ready.",
    }
