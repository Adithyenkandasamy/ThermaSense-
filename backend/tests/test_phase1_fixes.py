"""
Phase 1 Foundation Fix Tests
=============================
Focused tests for the four fixes applied in Phase 1:

  1. Land-cover async fix  — context_service uses lookup_land_cover_async
  2. Facility sync         — sync_facilities executes, dedup works, Overpass
                             failure falls back gracefully
  3. Demo mode             — demo data is correctly marked and never duplicates
  4. Environment config    — missing keys do not crash startup; keys are read
                             from the correct env var names

These tests are pure unit tests — no live database or network required.
"""

import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ===========================================================================
# 1. LAND COVER — async fix
# ===========================================================================
class TestLandCoverAsyncFix:
    """Verify the async land-cover path is used from context_service."""

    @pytest.mark.asyncio
    async def test_context_service_calls_async_function(self):
        """build_event_context() must call lookup_land_cover_async, not the sync wrapper."""
        from app.services import context_service

        event = MagicMock()
        event.id = 1
        event.latitude = 37.5
        event.longitude = -122.1

        # Mock the DB to return no facilities
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.execute.return_value.fetchall = MagicMock(return_value=[])

        # Patch lookup_land_cover_async to return a real land-cover value
        with patch.object(
            context_service,
            "lookup_land_cover_async",
            new=AsyncMock(return_value={"land_cover": "FOREST", "source": "NOMINATIM"}),
        ) as mock_async:
            result = await context_service.build_event_context(event, mock_db)

        mock_async.assert_called_once_with(37.5, -122.1)
        assert result["land_cover"] == "FOREST", (
            "land_cover must come from lookup_land_cover_async, not be UNKNOWN"
        )

    @pytest.mark.asyncio
    async def test_land_cover_not_always_unknown(self):
        """After the fix the land_cover field must reflect whatever the async lookup returns."""
        from app.services import context_service

        event = MagicMock()
        event.id = 2
        event.latitude = 12.34
        event.longitude = 78.90

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.execute.return_value.fetchall = MagicMock(return_value=[])

        for expected in ("BUILT_UP", "CROPLAND", "GRASSLAND", "WATER", "BARE_LAND", "SNOW_ICE"):
            with patch.object(
                context_service,
                "lookup_land_cover_async",
                new=AsyncMock(return_value={"land_cover": expected, "source": "TEST"}),
            ):
                result = await context_service.build_event_context(event, mock_db)
            assert result["land_cover"] == expected, (
                f"Expected {expected}, got {result['land_cover']}"
            )

    @pytest.mark.asyncio
    async def test_land_cover_exception_returns_unknown(self):
        """If lookup_land_cover_async raises, land_cover gracefully falls back to UNKNOWN."""
        from app.services import context_service

        event = MagicMock()
        event.id = 3
        event.latitude = 37.5
        event.longitude = -122.1

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.execute.return_value.fetchall = MagicMock(return_value=[])

        with patch.object(
            context_service,
            "lookup_land_cover_async",
            new=AsyncMock(side_effect=RuntimeError("network timeout")),
        ):
            result = await context_service.build_event_context(event, mock_db)

        assert result["land_cover"] == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_lookup_land_cover_async_is_callable_without_running_loop_error(self):
        """
        lookup_land_cover_async itself must be awaitable and must not raise
        because it detects a running event loop (that was the old sync bug).
        """
        from app.ingestion.landcover import lookup_land_cover_async

        # Patch httpx so no real network call is made
        with patch("app.ingestion.landcover._try_open_meteo", new=AsyncMock(return_value=None)):
            with patch("app.ingestion.landcover._try_nominatim", new=AsyncMock(return_value=None)):
                result = await lookup_land_cover_async(37.5, -122.1)

        # Must return a dict with land_cover key — heuristic fallback is fine
        assert isinstance(result, dict)
        assert "land_cover" in result
        assert result["land_cover"] != "UNKNOWN" or result.get("source") == "HEURISTIC", (
            "Result must come from the heuristic, not the old sync-loop bail-out"
        )

    def test_sync_wrapper_still_works_outside_async(self):
        """The sync wrapper lookup_land_cover still works for non-async callers."""
        from app.ingestion.landcover import lookup_land_cover

        # Invalid coords still return UNKNOWN
        assert lookup_land_cover(999, 999) == "UNKNOWN"


# ===========================================================================
# 2. FACILITY SYNC
# ===========================================================================
class TestFacilitySync:
    """Verify sync_facilities executes, deduplicates, and handles Overpass failure."""

    @pytest.mark.asyncio
    async def test_sync_facilities_with_overpass_success(self):
        """When Overpass returns data, facilities are parsed and upserted."""
        from app.ingestion.facilities import sync_facilities

        mock_elements = [
            {
                "type": "node",
                "id": 111,
                "lat": 37.5,
                "lon": -122.1,
                "tags": {"name": "Test Power Plant", "power": "plant"},
            }
        ]

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.execute.return_value.fetchone = MagicMock(return_value=(1,))
        mock_db.flush = AsyncMock()

        with patch("app.ingestion.facilities._fetch_overpass", new=AsyncMock(return_value=mock_elements)):
            result = await sync_facilities(mock_db)

        assert result["status"] == "ok"
        assert result["source"] == "OSM"
        assert result["fetched"] >= 1

    @pytest.mark.asyncio
    async def test_sync_facilities_overpass_failure_uses_demo_fallback(self):
        """When Overpass returns empty, sync_facilities falls back to DEMO facilities."""
        from app.ingestion.facilities import sync_facilities

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.execute.return_value.fetchone = MagicMock(return_value=(1,))
        mock_db.flush = AsyncMock()

        with patch("app.ingestion.facilities._fetch_overpass", new=AsyncMock(return_value=[])):
            result = await sync_facilities(mock_db)

        assert result["status"] == "ok"
        assert result["source"] == "DEMO_FALLBACK"
        assert result["fetched"] > 0

    @pytest.mark.asyncio
    async def test_sync_facilities_does_not_raise_on_overpass_timeout(self):
        """An Overpass network exception must not propagate — falls back to demo."""
        from app.ingestion.facilities import _fetch_overpass

        # _fetch_overpass catches its own exceptions and returns []
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=TimeoutError("Overpass timeout"))
            mock_client_cls.return_value = mock_client

            result = await _fetch_overpass((-124.5, 32.5, -114.0, 42.0))

        assert result == [], "Overpass failure must return empty list, not raise"

    def test_parse_elements_deduplication(self):
        """Duplicate OSM IDs within one Overpass response are deduplicated."""
        from app.ingestion.facilities import _parse_elements

        elements = [
            {"type": "node", "id": 42, "lat": 37.0, "lon": -122.0,
             "tags": {"name": "Plant A", "power": "plant"}},
            {"type": "node", "id": 42, "lat": 37.0, "lon": -122.0,
             "tags": {"name": "Plant A Duplicate", "power": "plant"}},
        ]
        facilities = _parse_elements(elements)
        assert len(facilities) == 1, "Duplicate external_id must be deduplicated"

    @pytest.mark.asyncio
    async def test_startup_sync_failure_is_non_fatal(self):
        """_sync_facilities_on_startup catches exceptions and never raises."""
        from app.main import _sync_facilities_on_startup

        with patch("app.main._sync_facilities_on_startup", wraps=_sync_facilities_on_startup):
            with patch("app.database.AsyncSessionLocal") as mock_session_cls:
                mock_session = AsyncMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=False)
                mock_session.commit = AsyncMock(side_effect=Exception("DB offline"))
                mock_session_cls.return_value = mock_session

                # Must not raise
                try:
                    await _sync_facilities_on_startup()
                    raised = False
                except Exception:
                    raised = True

        assert not raised, "_sync_facilities_on_startup must not propagate exceptions"


# ===========================================================================
# 3. DEMO MODE
# ===========================================================================
class TestDemoMode:
    """Verify demo data markers and duplicate prevention."""

    def test_demo_events_have_unique_hotspot_keys(self):
        """All 6 demo events must have unique (lat, lon, acq_date, acq_time) tuples."""
        from app.services.demo_data_service import DEMO_EVENTS

        keys = [
            (e["latitude"], e["longitude"], e["acq_date"], e["acq_time"])
            for e in DEMO_EVENTS
        ]
        assert len(keys) == len(set(keys)), (
            "Demo events must have unique uq_hotspot keys to prevent spurious duplicates"
        )

    def test_demo_events_marked_with_demo_source(self):
        """seed_demo_data must set source='DEMO' so events can never be mistaken for FIRMS data."""
        import inspect
        from app.services import demo_data_service

        src = inspect.getsource(demo_data_service.seed_demo_data)
        assert '"DEMO"' in src or "'DEMO'" in src, (
            "seed_demo_data must set source='DEMO' on ThermalEvent rows"
        )

    def test_demo_events_have_satellite_marker(self):
        """seed_demo_data sets satellite='DEMO-SAT' — never mistaken for real FIRMS satellite."""
        import inspect
        from app.services import demo_data_service

        src = inspect.getsource(demo_data_service.seed_demo_data)
        assert "DEMO-SAT" in src, (
            "Demo events must use satellite='DEMO-SAT', not a real FIRMS satellite name"
        )

    def test_demo_events_have_engine_version_marker(self):
        """EventAnalysis seeded by demo uses engine_version='demo-v1'."""
        import inspect
        from app.services import demo_data_service

        src = inspect.getsource(demo_data_service.seed_demo_data)
        assert "demo-v1" in src

    def test_demo_seeding_guard_in_ingest_service(self):
        """seed_demo_data is only called when FIRMS key is absent."""
        import inspect
        from app.services import ingest_service

        src = inspect.getsource(ingest_service.run_ingestion)
        assert "firms_api_key" in src, (
            "run_ingestion must check firms_api_key before falling back to demo"
        )
        assert "seed_demo_data" in src

    @pytest.mark.asyncio
    async def test_demo_seeding_idempotent_second_call_inserts_nothing(self):
        """
        Simulated second call: all ON CONFLICT DO NOTHING paths return no rows,
        so inserted counts are 0 — confirms idempotency without a live DB.
        """
        from app.services.demo_data_service import seed_demo_data
        from app.models.thermal_event import ThermalEvent, EventAnalysis

        # Simulate: all upserts hit the conflict path (fetchone returns None)
        mock_execute_result = MagicMock()
        mock_execute_result.fetchone = MagicMock(return_value=None)  # conflict → skip
        mock_execute_result.scalars = MagicMock()
        mock_execute_result.scalars.return_value.all = MagicMock(return_value=[])  # no DEMO events

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_execute_result)
        mock_db.flush = AsyncMock()

        result = await seed_demo_data(mock_db)

        assert result["facilities_inserted"] == 0
        assert result["events_inserted"] == 0
        assert result["analyses_inserted"] == 0
        assert result["demo"] is True


# ===========================================================================
# 4. ENVIRONMENT CONFIGURATION
# ===========================================================================
class TestEnvironmentConfig:
    """Verify env var names and safe defaults."""

    def test_firms_key_reads_from_firms_map_key(self):
        """FIRMS_MAP_KEY env var must populate firms_api_key."""
        import importlib
        from unittest.mock import patch as _patch

        with _patch.dict("os.environ", {"FIRMS_MAP_KEY": "test-firms-key"}, clear=False):
            from pydantic_settings import BaseSettings
            from app.config import Settings

            s = Settings()
            assert s.firms_api_key == "test-firms-key"

    def test_firms_key_reads_from_firms_api_key_alias(self):
        """FIRMS_API_KEY alias must also populate firms_api_key."""
        with patch.dict("os.environ", {"FIRMS_API_KEY": "alias-firms-key"}, clear=False):
            from app.config import Settings

            s = Settings()
            assert s.firms_api_key == "alias-firms-key"

    def test_groq_key_reads_from_llm_api_key(self):
        """LLM_API_KEY env var must populate groq_api_key."""
        with patch.dict("os.environ", {"LLM_API_KEY": "test-groq-key"}, clear=False):
            from app.config import Settings

            s = Settings()
            assert s.groq_api_key == "test-groq-key"

    def test_groq_key_reads_from_groq_api_key_alias(self):
        """GROQ_API_KEY alias must also populate groq_api_key."""
        with patch.dict("os.environ", {"GROQ_API_KEY": "alias-groq-key"}, clear=False):
            from app.config import Settings

            s = Settings()
            assert s.groq_api_key == "alias-groq-key"

    def test_missing_firms_key_defaults_to_empty_string(self):
        """Missing FIRMS key must default to '' — no crash, triggers demo mode."""
        env = {k: v for k, v in __import__("os").environ.items()
               if k not in ("FIRMS_MAP_KEY", "FIRMS_API_KEY")}
        with patch.dict("os.environ", env, clear=True):
            from app.config import Settings

            s = Settings()
            assert s.firms_api_key == ""

    def test_missing_groq_key_defaults_to_empty_string(self):
        """Missing Groq key must default to '' — no crash, triggers fallback mode."""
        env = {k: v for k, v in __import__("os").environ.items()
               if k not in ("LLM_API_KEY", "GROQ_API_KEY")}
        with patch.dict("os.environ", env, clear=True):
            from app.config import Settings

            s = Settings()
            assert s.groq_api_key == ""

    def test_no_keys_does_not_crash_settings_load(self):
        """Settings must load without raising even when both API keys are absent."""
        env = {k: v for k, v in __import__("os").environ.items()
               if k not in ("FIRMS_MAP_KEY", "FIRMS_API_KEY", "LLM_API_KEY", "GROQ_API_KEY")}
        with patch.dict("os.environ", env, clear=True):
            from app.config import Settings

            try:
                s = Settings()
                crashed = False
            except Exception as e:
                crashed = True

        assert not crashed, "Settings must not crash when API keys are missing"
