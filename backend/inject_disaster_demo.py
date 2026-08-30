"""
ThermaSense — Disaster-Scale Demo Data Injector
================================================
Injects 4 high-severity real-world thermal disaster scenarios directly into
the PostgreSQL database so they immediately appear as map markers.

Each scenario represents a distinct cause type:
  1. VEGETATION_FIRE   — Uttarakhand Forest Fire Corridor (India)
  2. AGRICULTURAL_BURNING — Punjab Stubble Burning Crisis (India)
  3. INDUSTRIAL_HEAT   — Jharkhand Steel Belt Smelter Overload
  4. GAS_FLARE         — Assam Oil Field Flare Runaway

Run: python inject_disaster_demo.py
"""

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

# ─────────────────────────────────────────────────────────────────────────────
# Disaster scenarios: each entry is one distinct real-location cluster.
# All FRP values are extreme (disaster-grade), matching real wildfire events.
# ─────────────────────────────────────────────────────────────────────────────
DISASTER_SCENARIOS = [

    # ── SCENARIO 1: Uttarakhand Forest Fire (India) ───────────────────────
    # Based on the April 2024 Uttarakhand forest fire event.
    # 1,073 sq km of forest burned across Nainital, Chamoli, Tehri.
    {
        "label": "VEGETATION FIRE — Uttarakhand Forest Fire Corridor",
        "observations": [
            {"lat": 29.641, "lon": 79.460, "frp": 318.7, "brightness": 412.3, "bright_ti4": 415.1, "daynight": "D", "confidence": "high"},
            {"lat": 29.655, "lon": 79.481, "frp": 289.4, "brightness": 408.6, "bright_ti4": 411.2, "daynight": "D", "confidence": "high"},
            {"lat": 29.632, "lon": 79.473, "frp": 412.1, "brightness": 425.7, "bright_ti4": 428.3, "daynight": "D", "confidence": "high"},
            {"lat": 29.670, "lon": 79.505, "frp": 178.3, "brightness": 395.2, "bright_ti4": 397.8, "daynight": "D", "confidence": "nominal"},
            {"lat": 29.618, "lon": 79.449, "frp": 534.8, "brightness": 438.9, "bright_ti4": 441.5, "daynight": "D", "confidence": "high"},
            {"lat": 30.021, "lon": 79.232, "frp": 220.5, "brightness": 401.1, "bright_ti4": 403.6, "daynight": "D", "confidence": "high"},
            {"lat": 30.048, "lon": 79.251, "frp": 195.3, "brightness": 397.4, "bright_ti4": 399.9, "daynight": "D", "confidence": "nominal"},
        ],
        "source": "VIIRS_NOAA20_NRT",
        "satellite": "N20",
        "acq_date": "2026-08-30",
        "acq_time": "0545",
    },

    # ── SCENARIO 2: Punjab Stubble Burning Crisis ─────────────────────────
    # Based on post-Kharif crop harvest October stubble burning (Amritsar / Ludhiana)
    {
        "label": "AGRICULTURAL BURNING — Punjab Stubble Burning Crisis",
        "observations": [
            {"lat": 31.142, "lon": 74.874, "frp":  28.4, "brightness": 335.2, "bright_ti4": 337.6, "daynight": "D", "confidence": "high"},
            {"lat": 31.156, "lon": 74.892, "frp":  32.1, "brightness": 338.4, "bright_ti4": 340.1, "daynight": "D", "confidence": "high"},
            {"lat": 31.168, "lon": 74.911, "frp":  21.7, "brightness": 328.9, "bright_ti4": 330.4, "daynight": "D", "confidence": "nominal"},
            {"lat": 30.912, "lon": 75.843, "frp":  41.5, "brightness": 342.6, "bright_ti4": 345.2, "daynight": "D", "confidence": "high"},
            {"lat": 30.934, "lon": 75.861, "frp":  35.8, "brightness": 339.1, "bright_ti4": 341.8, "daynight": "D", "confidence": "high"},
            {"lat": 30.891, "lon": 75.822, "frp":  27.3, "brightness": 333.4, "bright_ti4": 335.9, "daynight": "D", "confidence": "nominal"},
            {"lat": 31.323, "lon": 74.621, "frp":  19.6, "brightness": 326.7, "bright_ti4": 328.3, "daynight": "D", "confidence": "nominal"},
            {"lat": 31.346, "lon": 74.640, "frp":  24.8, "brightness": 331.2, "bright_ti4": 333.7, "daynight": "D", "confidence": "high"},
        ],
        "source": "VIIRS_NOAA21_NRT",
        "satellite": "N21",
        "acq_date": "2026-08-30",
        "acq_time": "0615",
    },

    # ── SCENARIO 3: Jharkhand Steel Belt Industrial Overload ──────────────
    # Based on Jamshedpur / Bokaro steel plant excessive heat discharge events
    {
        "label": "INDUSTRIAL HEAT — Jharkhand Steel Belt Smelter Overload",
        "observations": [
            {"lat": 22.806, "lon": 86.187, "frp":  87.4, "brightness": 378.3, "bright_ti4": 381.2, "daynight": "N", "confidence": "high"},
            {"lat": 22.812, "lon": 86.194, "frp":  95.1, "brightness": 383.7, "bright_ti4": 386.4, "daynight": "N", "confidence": "high"},
            {"lat": 22.799, "lon": 86.180, "frp":  71.6, "brightness": 371.2, "bright_ti4": 374.1, "daynight": "N", "confidence": "nominal"},
            {"lat": 23.668, "lon": 85.940, "frp": 112.3, "brightness": 391.8, "bright_ti4": 394.5, "daynight": "N", "confidence": "high"},
            {"lat": 23.681, "lon": 85.958, "frp": 103.7, "brightness": 388.4, "bright_ti4": 391.2, "daynight": "N", "confidence": "high"},
        ],
        "source": "VIIRS_NOAA20_NRT",
        "satellite": "N20",
        "acq_date": "2026-08-30",
        "acq_time": "1930",
    },

    # ── SCENARIO 4: Assam Oil Field Gas Flare Runaway ─────────────────────
    # Based on Digboi / Duliajan oil fields in Assam — gas venting/flaring events
    {
        "label": "GAS FLARE — Assam Oil Field Flare Runaway",
        "observations": [
            {"lat": 27.391, "lon": 95.618, "frp": 156.8, "brightness": 432.4, "bright_ti4": 435.7, "daynight": "N", "confidence": "high"},
            {"lat": 27.398, "lon": 95.631, "frp": 143.2, "brightness": 428.9, "bright_ti4": 432.1, "daynight": "N", "confidence": "high"},
            {"lat": 27.384, "lon": 95.607, "frp": 168.4, "brightness": 437.2, "bright_ti4": 440.3, "daynight": "N", "confidence": "high"},
            {"lat": 27.396, "lon": 95.623, "frp": 134.7, "brightness": 424.3, "bright_ti4": 427.6, "daynight": "N", "confidence": "nominal"},
            {"lat": 27.402, "lon": 95.640, "frp": 119.5, "brightness": 418.7, "bright_ti4": 421.8, "daynight": "N", "confidence": "nominal"},
        ],
        "source": "VIIRS_NOAA21_NRT",
        "satellite": "N21",
        "acq_date": "2026-08-30",
        "acq_time": "2015",
    },
]


def _make_hash(lat: float, lon: float, acq_date: str, acq_time: str, satellite: str) -> str:
    """SHA-256 hash matching the production observation_normalizer logic."""
    raw = f"{lat}|{lon}|{acq_date}|{acq_time}|{satellite}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def inject_all():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    total_inserted = 0
    total_skipped = 0

    async with async_session() as session:
        for scenario in DISASTER_SCENARIOS:
            print(f"\n  Injecting: {scenario['label']}")
            scenario_inserted = 0
            scenario_skipped = 0

            for obs in scenario["observations"]:
                obs_hash = _make_hash(
                    obs["lat"], obs["lon"],
                    scenario["acq_date"], scenario["acq_time"],
                    scenario["satellite"],
                )

                # Check duplicate
                exists = await session.execute(
                    text("SELECT 1 FROM thermal_observations WHERE observation_hash = :h"),
                    {"h": obs_hash},
                )
                if exists.scalar():
                    scenario_skipped += 1
                    continue

                obs_id = uuid.uuid4()
                acq_dt = datetime.strptime(
                    f"{scenario['acq_date']} {scenario['acq_time'][:2]}:{scenario['acq_time'][2:]}",
                    "%Y-%m-%d %H:%M"
                ).replace(tzinfo=timezone.utc)

                await session.execute(
                    text("""
                        INSERT INTO thermal_observations
                          (id, source, latitude, longitude,
                           acquisition_datetime, acq_date, acq_time,
                           satellite, instrument,
                           brightness, bright_ti4, bright_ti5, frp,
                           confidence, daynight,
                           raw_data, observation_hash,
                           created_at, updated_at)
                        VALUES
                          (:id, :source, :lat, :lon,
                           :acq_dt, :acq_date, :acq_time,
                           :satellite, 'VIIRS',
                           :brightness, :bright_ti4, NULL, :frp,
                           :confidence, :daynight,
                           :raw_data, :obs_hash,
                           NOW(), NOW())
                    """),
                    {
                        "id": obs_id,
                        "source": scenario["source"],
                        "lat": obs["lat"],
                        "lon": obs["lon"],
                        "acq_dt": acq_dt,
                        "acq_date": scenario["acq_date"],
                        "acq_time": scenario["acq_time"],
                        "satellite": scenario["satellite"],
                        "brightness": obs["brightness"],
                        "bright_ti4": obs["bright_ti4"],
                        "frp": obs["frp"],
                        "confidence": obs["confidence"],
                        "daynight": obs["daynight"],
                        "raw_data": f'{{"demo": true, "scenario": "{scenario["label"]}"}}',
                        "obs_hash": obs_hash,
                    },
                )
                scenario_inserted += 1

            await session.commit()
            print(f"    -> Inserted: {scenario_inserted}  |  Skipped (duplicates): {scenario_skipped}")
            total_inserted += scenario_inserted
            total_skipped += scenario_skipped

    print(f"\n{'='*60}")
    print(f"  TOTAL INSERTED : {total_inserted} disaster-scale observations")
    print(f"  TOTAL SKIPPED  : {total_skipped} (already in DB)")
    print(f"  -> Open http://localhost:3000 and Ctrl+Shift+R to see them on the map!")
    print(f"{'='*60}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(inject_all())
