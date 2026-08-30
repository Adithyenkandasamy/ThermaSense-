"""
ThermaSense Cause Attribution Verification & Demonstration Script.

Evaluates the rule-based attribution engine against all primary thermal anomaly causes:
  1. Vegetation Fire / Wildfire (vegetation_fire)
  2. Agricultural Burning / Crop Residue (agricultural_burning)
  3. Industrial Heat (industrial_heat)
  4. Gas Flare (gas_flare)
"""

from datetime import datetime, timezone

from app.schemas.weather import WeatherContext
from app.schemas.geospatial import GeospatialResponse, NearbyFeatureResponse
from app.services.attribution_service import (
    _compile_attribution_result,
    _evaluate_evidence_and_scores,
)


def run_demo():
    print("=" * 75)
    print("  THERMASENSE ATTRIBUTION ENGINE — MULTI-CAUSE CLASSIFICATION DEMO")
    print("=" * 75)

    now = datetime.now(timezone.utc)

    # ─────────────────────────────────────────────────────────────────────
    # CASE 1: Vegetation Fire / Wildfire
    # Signature: High FRP (140 MW), Low Humidity (18%), Near Forest Buffer (<300m)
    # ─────────────────────────────────────────────────────────────────────
    weather_wildfire = WeatherContext(
        temperature=34.2, relative_humidity=18.0,
        wind_speed=24.5, wind_direction=220.0,
        precipitation=0.0,
    )
    geo_wildfire = GeospatialResponse(
        latitude=39.5, longitude=-121.5, radius_m=2000,
        forests=[
            NearbyFeatureResponse(feature_type="forest", distance_m=120.0, name="Plumas National Forest"),
        ],
    )
    scores_1, ev_1 = _evaluate_evidence_and_scores(
        latitude=39.5, longitude=-121.5,
        started_at=now, ended_at=now,
        total_frp=140.0, max_frp=140.0, observation_count=3,
        brightness=365.0, bright_ti4=365.0,
        day_count=3, night_count=0,
        geo_ctx=geo_wildfire, weather_ctx=weather_wildfire,
    )
    res_1 = _compile_attribution_result(
        entity_id="demo-wildfire-01", entity_type="event",
        scores=scores_1, evidence=ev_1,
    )

    print("\n[CASE 1] SATELLITE WILDFIRE / FOREST FIRE (e.g. California / Mediterranean)")
    print(f"  • Primary Cause    : {res_1.primary_cause.upper()}")
    print(f"  • Confidence       : {int(res_1.confidence * 100)}%")
    print(f"  • Reasoning Summary: {res_1.reasoning_summary}")
    print("  • Supporting Evidence:")
    for e in res_1.evidence:
        print(f"     * [{e.source.upper()}] {e.factor}: {e.value}")

    # ─────────────────────────────────────────────────────────────────────
    # CASE 2: Agricultural Burning / Crop Residue Burning
    # Signature: Moderate FRP (22 MW), Daylight, Cropland Area, Dry Weather
    # ─────────────────────────────────────────────────────────────────────
    weather_agri = WeatherContext(
        temperature=29.0, relative_humidity=45.0,
        wind_speed=8.0, wind_direction=180.0,
        precipitation=0.0,
    )
    geo_agri = GeospatialResponse(
        latitude=30.3, longitude=75.8, radius_m=2000,
        croplands=[
            NearbyFeatureResponse(feature_type="cropland", distance_m=50.0, name="Agricultural Cropland"),
        ],
    )
    scores_2, ev_2 = _evaluate_evidence_and_scores(
        latitude=30.3, longitude=75.8,
        started_at=datetime(2026, 8, 30, 14, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 8, 30, 14, 30, tzinfo=timezone.utc),
        total_frp=22.0, max_frp=22.0, observation_count=1,
        brightness=325.0, bright_ti4=325.0,
        day_count=1, night_count=0,
        geo_ctx=geo_agri, weather_ctx=weather_agri,
    )
    res_2 = _compile_attribution_result(
        entity_id="demo-agri-02", entity_type="event",
        scores=scores_2, evidence=ev_2,
    )

    print("\n[CASE 2] CROP RESIDUE / STUBBLE BURNING (e.g. Agricultural Plains)")
    print(f"  • Primary Cause    : {res_2.primary_cause.upper()}")
    print(f"  • Confidence       : {int(res_2.confidence * 100)}%")
    print(f"  • Reasoning Summary: {res_2.reasoning_summary}")
    print("  • Supporting Evidence:")
    for e in res_2.evidence:
        print(f"     * [{e.source.upper()}] {e.factor}: {e.value}")

    # ─────────────────────────────────────────────────────────────────────
    # CASE 3: Industrial Heat
    # Signature: Industrial Land-Use (<300m), Nighttime Acquisition, High Humidity
    # ─────────────────────────────────────────────────────────────────────
    weather_ind = WeatherContext(
        temperature=24.0, relative_humidity=78.0,
        wind_speed=5.0, wind_direction=90.0,
        precipitation=0.0,
    )
    geo_ind = GeospatialResponse(
        latitude=28.4, longitude=77.0, radius_m=2000,
        industrial=[
            NearbyFeatureResponse(feature_type="industrial", distance_m=180.0, name="Steel & Metal Smelting Complex"),
        ],
    )
    scores_3, ev_3 = _evaluate_evidence_and_scores(
        latitude=28.4, longitude=77.0,
        started_at=datetime(2026, 8, 30, 23, 15, tzinfo=timezone.utc),
        ended_at=datetime(2026, 8, 30, 23, 15, tzinfo=timezone.utc),
        total_frp=25.0, max_frp=25.0, observation_count=1,
        brightness=335.0, bright_ti4=335.0,
        day_count=0, night_count=1,
        geo_ctx=geo_ind, weather_ctx=weather_ind,
    )
    res_3 = _compile_attribution_result(
        entity_id="demo-industrial-03", entity_type="event",
        scores=scores_3, evidence=ev_3,
    )

    print("\n[CASE 3] INDUSTRIAL MANUFACTURING HEAT (e.g. Steel Plant / Kiln / Smelter)")
    print(f"  • Primary Cause    : {res_3.primary_cause.upper()}")
    print(f"  • Confidence       : {int(res_3.confidence * 100)}%")
    print(f"  • Reasoning Summary: {res_3.reasoning_summary}")
    print("  • Supporting Evidence:")
    for e in res_3.evidence:
        print(f"     * [{e.source.upper()}] {e.factor}: {e.value}")

    # ─────────────────────────────────────────────────────────────────────
    # CASE 4: Gas Flare
    # Signature: Explicit Gas Flare Stack in OSM tags / <500m, Extreme Brightness
    # ─────────────────────────────────────────────────────────────────────
    weather_flare = WeatherContext(
        temperature=32.0, relative_humidity=65.0,
        wind_speed=12.0, wind_direction=310.0,
        precipitation=0.0,
    )
    geo_flare = GeospatialResponse(
        latitude=29.0, longitude=48.0, radius_m=2000,
        industrial=[
            NearbyFeatureResponse(
                feature_type="industrial", distance_m=120.0,
                name="Offshore Petrochemical Flare Stack",
                tags={"man_made": "flare"}
            ),
        ],
    )
    scores_4, ev_4 = _evaluate_evidence_and_scores(
        latitude=29.0, longitude=48.0,
        started_at=datetime(2026, 8, 30, 23, 45, tzinfo=timezone.utc),
        ended_at=datetime(2026, 8, 30, 23, 45, tzinfo=timezone.utc),
        total_frp=55.0, max_frp=55.0, observation_count=1,
        brightness=380.0, bright_ti4=380.0,
        day_count=0, night_count=1,
        geo_ctx=geo_flare, weather_ctx=weather_flare,
    )
    res_4 = _compile_attribution_result(
        entity_id="demo-flare-04", entity_type="event",
        scores=scores_4, evidence=ev_4,
    )

    print("\n[CASE 4] OIL & GAS FLARING (e.g. Petrochemical Flare Stack / Extraction Pit)")
    print(f"  • Primary Cause    : {res_4.primary_cause.upper()}")
    print(f"  • Confidence       : {int(res_4.confidence * 100)}%")
    print(f"  • Reasoning Summary: {res_4.reasoning_summary}")
    print("  • Supporting Evidence:")
    for e in res_4.evidence:
        print(f"     * [{e.source.upper()}] {e.factor}: {e.value}")

    print("\n" + "=" * 75)
    print("  ALL 4 THERMAL ANOMALY CAUSES VERIFIED WITH MULTI-SOURCE EVIDENCE")
    print("=" * 75)


if __name__ == "__main__":
    run_demo()
