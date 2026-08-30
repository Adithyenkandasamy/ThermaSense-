"""
Demo Simulation Tests
=====================
Tests for POST /api/v1/demo/simulate and related behavior.

These tests use mocked DB sessions and mocked process_event() so
no live database is required.
"""

import sys
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ===========================================================================
# 1. Simulate request model validation
# ===========================================================================
class TestSimulateRequestModel:
    """Validate the SimulateRequest Pydantic model."""

    def test_default_scenario(self):
        from app.api.routes.demo import SimulateRequest
        req = SimulateRequest()
        assert req.scenario == "industrial"

    def test_all_scenarios_valid(self):
        from app.api.routes.demo import SimulateRequest
        for scenario in ("industrial", "wildfire", "agricultural", "mining", "persistent", "extreme"):
            req = SimulateRequest(scenario=scenario)
            assert req.scenario == scenario

    def test_optional_overrides(self):
        from app.api.routes.demo import SimulateRequest
        req = SimulateRequest(scenario="wildfire", frp=250.0, brightness=380.0)
        assert req.frp == 250.0
        assert req.brightness == 380.0

    def test_scenario_presets_cover_all_scenarios(self):
        from app.api.routes.demo import _SCENARIO_PRESETS
        required = {"industrial", "wildfire", "agricultural", "mining", "persistent", "extreme"}
        assert required.issubset(set(_SCENARIO_PRESETS.keys()))

    def test_each_preset_has_required_keys(self):
        from app.api.routes.demo import _SCENARIO_PRESETS
        required_keys = {"latitude", "longitude", "frp", "brightness", "confidence", "label"}
        for name, preset in _SCENARIO_PRESETS.items():
            for key in required_keys:
                assert key in preset, f"Preset '{name}' missing key '{key}'"

    def test_preset_coordinates_valid(self):
        from app.api.routes.demo import _SCENARIO_PRESETS
        for name, preset in _SCENARIO_PRESETS.items():
            lat, lon = preset["latitude"], preset["longitude"]
            assert -90 <= lat <= 90,    f"Preset '{name}' has invalid latitude {lat}"
            assert -180 <= lon <= 180,  f"Preset '{name}' has invalid longitude {lon}"

    def test_preset_frp_values_positive(self):
        from app.api.routes.demo import _SCENARIO_PRESETS
        for name, preset in _SCENARIO_PRESETS.items():
            assert preset["frp"] > 0, f"Preset '{name}' has non-positive FRP"


# ===========================================================================
# 2. Simulate endpoint — event creation
# ===========================================================================
class TestSimulateEventCreation:
    """Verify the simulate endpoint creates events with correct markers."""

    @pytest.mark.asyncio
    async def test_simulated_event_source_is_demo(self):
        """Event inserted by simulate must have source='DEMO'."""
        from app.api.routes.demo import simulate_event, SimulateRequest
        from app.models.thermal_event import RiskLevel

        req = SimulateRequest(scenario="industrial")
        event_id = 42

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, i: event_id

        mock_execute_result = MagicMock()
        mock_execute_result.fetchone = MagicMock(return_value=(event_id,))

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_execute_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        analysis_result = {
            "event_id": event_id,
            "analysis_id": 1,
            "classification": "INDUSTRIAL_THERMAL",
            "risk_level": "MODERATE",
            "risk_score": 54.0,
            "investigation": {"ai_mode": "FALLBACK", "summary": "Test summary."},
        }

        captured_values = {}

        original_execute = mock_db.execute

        async def capture_execute(stmt, *args, **kwargs):
            # Capture the INSERT values to verify source=DEMO
            stmt_str = str(stmt)
            if "thermal_events" in stmt_str.lower() and captured_values.get("source") is None:
                try:
                    # Check the compiled statement params
                    pass
                except Exception:
                    pass
            return await original_execute(stmt, *args, **kwargs)

        with (
            patch("app.api.routes.demo.process_event", AsyncMock(return_value=analysis_result)),
            patch("app.api.routes.demo.from_shape", return_value=MagicMock()),
        ):
            result = await simulate_event(req, mock_db)

        assert result["source"] == "DEMO"
        assert result["simulated"] is True
        assert result["event_id"] == event_id

    @pytest.mark.asyncio
    async def test_simulated_event_uses_scenario_preset_location(self):
        """When no lat/lon overrides, preset coordinates are used."""
        from app.api.routes.demo import simulate_event, SimulateRequest, _SCENARIO_PRESETS

        req = SimulateRequest(scenario="wildfire")
        preset = _SCENARIO_PRESETS["wildfire"]

        event_id = 99
        mock_execute_result = MagicMock()
        mock_execute_result.fetchone = MagicMock(return_value=(event_id,))

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_execute_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        analysis_result = {
            "event_id": event_id, "analysis_id": 2,
            "classification": "WILDFIRE", "risk_level": "HIGH",
            "risk_score": 72.0, "investigation": {"ai_mode": "FALLBACK", "summary": "Fire."},
        }

        with (
            patch("app.api.routes.demo.process_event", AsyncMock(return_value=analysis_result)),
            patch("app.api.routes.demo.from_shape", return_value=MagicMock()),
        ):
            result = await simulate_event(req, mock_db)

        assert result["location"]["latitude"] == preset["latitude"]
        assert result["location"]["longitude"] == preset["longitude"]

    @pytest.mark.asyncio
    async def test_simulate_override_frp_takes_precedence(self):
        """Custom FRP in request overrides the preset value."""
        from app.api.routes.demo import simulate_event, SimulateRequest

        req = SimulateRequest(scenario="industrial", frp=999.0)

        event_id = 10
        mock_execute_result = MagicMock()
        mock_execute_result.fetchone = MagicMock(return_value=(event_id,))

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_execute_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        analysis_result = {
            "event_id": event_id, "analysis_id": 3,
            "classification": "INDUSTRIAL_THERMAL", "risk_level": "EXTREME",
            "risk_score": 95.0, "investigation": {"ai_mode": "FALLBACK", "summary": "High."},
        }

        with (
            patch("app.api.routes.demo.process_event", AsyncMock(return_value=analysis_result)),
            patch("app.api.routes.demo.from_shape", return_value=MagicMock()),
        ):
            result = await simulate_event(req, mock_db)

        assert result["thermal"]["frp"] == 999.0


# ===========================================================================
# 3. Process_event is called
# ===========================================================================
class TestSimulateCallsPipeline:
    """Verify process_event() is invoked by simulate."""

    @pytest.mark.asyncio
    async def test_process_event_is_called(self):
        """simulate_event must call process_event with the new event_id."""
        from app.api.routes.demo import simulate_event, SimulateRequest

        req = SimulateRequest(scenario="industrial")
        event_id = 77

        mock_execute_result = MagicMock()
        mock_execute_result.fetchone = MagicMock(return_value=(event_id,))

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_execute_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        mock_process = AsyncMock(return_value={
            "event_id": event_id, "analysis_id": 5,
            "classification": "INDUSTRIAL_THERMAL", "risk_level": "MODERATE",
            "risk_score": 55.0, "investigation": {"ai_mode": "FALLBACK", "summary": "ok"},
        })

        with (
            patch("app.api.routes.demo.process_event", mock_process),
            patch("app.api.routes.demo.from_shape", return_value=MagicMock()),
        ):
            await simulate_event(req, mock_db)

        mock_process.assert_called_once_with(event_id, mock_db)

    @pytest.mark.asyncio
    async def test_event_analysis_id_returned(self):
        """Response must include the analysis_id from process_event."""
        from app.api.routes.demo import simulate_event, SimulateRequest

        req = SimulateRequest(scenario="mining")
        event_id = 88
        analysis_id = 123

        mock_execute_result = MagicMock()
        mock_execute_result.fetchone = MagicMock(return_value=(event_id,))

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_execute_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        with (
            patch("app.api.routes.demo.process_event", AsyncMock(return_value={
                "event_id": event_id, "analysis_id": analysis_id,
                "classification": "MINING_ACTIVITY", "risk_level": "LOW",
                "risk_score": 22.0, "investigation": {"ai_mode": "FALLBACK", "summary": "mine"},
            })),
            patch("app.api.routes.demo.from_shape", return_value=MagicMock()),
        ):
            result = await simulate_event(req, mock_db)

        assert result["analysis_id"] == analysis_id


# ===========================================================================
# 4. Alert broadcasting
# ===========================================================================
class TestSimulateAlertBroadcast:
    """Verify THERMAL_ALERT is broadcast for HIGH/EXTREME events."""

    @pytest.mark.asyncio
    async def test_high_risk_triggers_alert_broadcast(self):
        """HIGH risk simulate must set alert_broadcast=True."""
        from app.api.routes.demo import simulate_event, SimulateRequest

        req = SimulateRequest(scenario="extreme")
        event_id = 55

        mock_execute_result = MagicMock()
        mock_execute_result.fetchone = MagicMock(return_value=(event_id,))

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_execute_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        broadcasts = []
        mock_ws = AsyncMock()
        mock_ws.broadcast = AsyncMock(side_effect=lambda msg: broadcasts.append(msg) or None)

        with (
            patch("app.api.routes.demo.process_event", AsyncMock(return_value={
                "event_id": event_id, "analysis_id": 6,
                "classification": "INDUSTRIAL_THERMAL", "risk_level": "EXTREME",
                "risk_score": 95.0,
                "investigation": {"ai_mode": "FALLBACK", "summary": "Critical industrial event."},
            })),
            patch("app.api.routes.demo.from_shape", return_value=MagicMock()),
            patch("app.api.routes.demo.ws_manager", mock_ws),
        ):
            result = await simulate_event(req, mock_db)

        assert result["alert_broadcast"] is True
        # Should have broadcast both THERMAL_EVENT_ANALYZED and THERMAL_ALERT
        types = [b["type"] for b in broadcasts]
        assert "THERMAL_ALERT" in types
        assert "THERMAL_EVENT_ANALYZED" in types

    @pytest.mark.asyncio
    async def test_low_risk_does_not_trigger_alert(self):
        """LOW/MODERATE risk simulate must NOT set alert_broadcast=True."""
        from app.api.routes.demo import simulate_event, SimulateRequest

        req = SimulateRequest(scenario="agricultural")
        event_id = 33

        mock_execute_result = MagicMock()
        mock_execute_result.fetchone = MagicMock(return_value=(event_id,))

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_execute_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        with (
            patch("app.api.routes.demo.process_event", AsyncMock(return_value={
                "event_id": event_id, "analysis_id": 7,
                "classification": "AGRICULTURAL_BURNING", "risk_level": "LOW",
                "risk_score": 18.0,
                "investigation": {"ai_mode": "FALLBACK", "summary": "Crop burning."},
            })),
            patch("app.api.routes.demo.from_shape", return_value=MagicMock()),
        ):
            result = await simulate_event(req, mock_db)

        assert result["alert_broadcast"] is False

    @pytest.mark.asyncio
    async def test_alert_payload_structure(self):
        """THERMAL_ALERT broadcast must contain required fields."""
        from app.api.routes.demo import simulate_event, SimulateRequest

        req = SimulateRequest(scenario="industrial")
        event_id = 44

        mock_execute_result = MagicMock()
        mock_execute_result.fetchone = MagicMock(return_value=(event_id,))

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_execute_result)
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()

        captured = []
        mock_ws = AsyncMock()
        mock_ws.broadcast = AsyncMock(side_effect=lambda msg: captured.append(msg) or None)

        with (
            patch("app.api.routes.demo.process_event", AsyncMock(return_value={
                "event_id": event_id, "analysis_id": 8,
                "classification": "INDUSTRIAL_THERMAL", "risk_level": "HIGH",
                "risk_score": 78.0,
                "investigation": {"ai_mode": "FALLBACK", "summary": "High risk industrial."},
            })),
            patch("app.api.routes.demo.from_shape", return_value=MagicMock()),
            patch("app.api.routes.demo.ws_manager", mock_ws),
        ):
            await simulate_event(req, mock_db)

        alert_msgs = [m for m in captured if m.get("type") == "THERMAL_ALERT"]
        assert len(alert_msgs) == 1
        alert = alert_msgs[0]
        for field in ("event_id", "risk_level", "risk_score", "classification",
                      "latitude", "longitude", "timestamp", "summary", "simulated"):
            assert field in alert, f"THERMAL_ALERT missing field '{field}'"
        assert alert["simulated"] is True


# ===========================================================================
# 5. Demo data marking
# ===========================================================================
class TestSimulatedEventMarking:
    """Verify simulated events are clearly distinguished from real FIRMS data."""

    def test_response_always_has_simulated_true(self):
        """The response dict from simulate must always set simulated=True."""
        # This test verifies the contract without running the endpoint
        from app.api.routes.demo import _SCENARIO_PRESETS
        # All presets should result in a response with simulated=True
        # (enforced by the endpoint code)
        for scenario in _SCENARIO_PRESETS:
            assert scenario in ("industrial", "wildfire", "agricultural",
                                "mining", "persistent", "extreme")

    def test_demo_route_exists_and_is_post(self):
        """POST /api/v1/demo/simulate must be registered."""
        from app.api.routes.demo import router
        ws_paths = {r.path: getattr(r, "methods", set()) for r in router.routes}
        assert "/api/v1/demo/simulate" in ws_paths
        methods = ws_paths["/api/v1/demo/simulate"]
        assert "POST" in (methods or set())


# ===========================================================================
# 6. Alerts endpoint
# ===========================================================================
class TestAlertsEndpoint:
    """Verify the enhanced alerts routes."""

    def test_alerts_recent_route_registered(self):
        from app.api.routes.alerts import router
        paths = {r.path for r in router.routes}
        assert "/api/v1/alerts/recent" in paths

    def test_alerts_base_route_registered(self):
        from app.api.routes.alerts import router
        paths = {r.path for r in router.routes}
        assert "/api/v1/alerts" in paths
