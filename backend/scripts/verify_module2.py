"""
Verification script for Module 2 — Data Processing & Management.

Exercises the complete real-world pipeline:
1. Initialize DB schema
2. Trigger live ingestion from NASA FIRMS Area API
3. Verify records stored
4. Trigger identical ingestion again
5. Verify duplicate records skipped
6. Query stored observations with pagination and filters
7. Retrieve single observation by UUID
8. Verify Module 1 live hotspot fetch still functions
"""

import asyncio
import json
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.database import Base
from app.services import observation_service
from app.services.firms_service import fetch_hotspots


async def main():
    settings = get_settings()
    print("=" * 60)
    print("ThermaSense Module 2 Verification")
    print("=" * 60)
    print(f"FIRMS MAP KEY configured: {'Yes' if settings.firms_map_key else 'No'}")
    print(f"Database URL: {settings.database_url}")

    # Use test SQLite database for standalone verification script
    test_db_url = "sqlite+aiosqlite:///thermasense_test.db"
    print(f"Using verification database: {test_db_url}")

    engine = create_async_engine(test_db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[OK] Database tables created successfully.")

    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    # ── Test 1: Live FIRMS Ingestion ──────────────────────────────
    print("\n--- Test 1: Live Ingestion from NASA FIRMS (Regional Sample) ---")
    async with session_factory() as session:
        # Sample area: California/Western US (bbox: -125,32,-114,42)
        summary1 = await observation_service.ingest_firms_data(
            session,
            source="VIIRS_NOAA20_NRT",
            area="-125,32,-114,42",
            day_range=1,
        )
        print(f"Ingestion 1 Result: {json.dumps(summary1, indent=2)}")
        assert summary1["status"] == "success"
        assert summary1["fetched"] >= 0
        assert summary1["stored"] == summary1["validated"]
        print(f"[OK] Ingested {summary1['stored']} new thermal observations.")

    # ── Test 2: Idempotent Ingestion / Duplicate Protection ───────
    print("\n--- Test 2: Duplicate Ingestion Check ---")
    async with session_factory() as session:
        summary2 = await observation_service.ingest_firms_data(
            session,
            source="VIIRS_NOAA20_NRT",
            area="-125,32,-114,42",
            day_range=1,
        )
        print(f"Ingestion 2 Result: {json.dumps(summary2, indent=2)}")
        assert summary2["status"] == "success"
        assert summary2["stored"] == 0, f"Expected 0 new records, got {summary2['stored']}"
        assert summary2["duplicates"] == summary2["validated"], "All validated records should be identified as duplicates"
        print(f"[OK] Deduplication verified: {summary2['duplicates']} duplicates safely skipped.")

    # ── Test 3: Query Stored Observations ─────────────────────────
    print("\n--- Test 3: Query Stored Observations with Pagination ---")
    async with session_factory() as session:
        observations, total = await observation_service.list_observations(
            session,
            limit=5,
            offset=0,
        )
        print(f"Total observations in DB: {total}")
        print(f"Fetched page of {len(observations)} records:")
        for obs in observations:
            print(f"  * ID={obs.id} | Sat={obs.satellite} | Lat={obs.latitude:.4f}, Lon={obs.longitude:.4f} | FRP={obs.frp} | Time={obs.acquisition_datetime}")
        assert total >= summary1["stored"]
        print("[OK] Paginated observation query verified.")

    # ── Test 4: Single Observation Retrieval ──────────────────────
    if observations:
        sample_id = observations[0].id
        print(f"\n--- Test 4: Single Observation Retrieval by UUID ({sample_id}) ---")
        async with session_factory() as session:
            retrieved = await observation_service.get_observation(session, sample_id)
            assert retrieved is not None
            assert retrieved.id == sample_id
            print(f"[OK] Retrieved observation: Lat={retrieved.latitude}, Lon={retrieved.longitude}, Hash={retrieved.observation_hash[:16]}...")

    # ── Test 5: Module 1 Live Hotspots Endpoint Backward Compatibility ─
    print("\n--- Test 5: Module 1 Live Fetch Compatibility ---")
    hotspots, source_name, area_used = await fetch_hotspots(
        map_key=settings.firms_map_key,
        satellite="NOAA-20",
        day_range=1,
        area="-125,32,-114,42",
    )
    print(f"[OK] Module 1 live fetch returned {len(hotspots)} hotspots from {source_name}.")

    await engine.dispose()
    if os.path.exists("thermasense_test.db"):
        os.remove("thermasense_test.db")

    print("\n" + "=" * 60)
    print("ALL MODULE 2 PIPELINE VERIFICATIONS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
