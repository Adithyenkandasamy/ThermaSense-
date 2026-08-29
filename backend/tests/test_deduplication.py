"""
Unit tests for observation deduplication logic.
"""

from app.services.observation_normalizer import _generate_observation_hash, normalize_row


def test_deterministic_hash_generation():
    """Identical fields produce the exact same hash."""
    h1 = _generate_observation_hash(
        source="VIIRS_NOAA20_NRT",
        latitude=34.0522,
        longitude=-118.2437,
        acq_date="2026-08-29",
        acq_time="1430",
        satellite="NOAA-20",
        instrument="VIIRS",
    )
    h2 = _generate_observation_hash(
        source="VIIRS_NOAA20_NRT",
        latitude=34.0522,
        longitude=-118.2437,
        acq_date="2026-08-29",
        acq_time="1430",
        satellite="NOAA-20",
        instrument="VIIRS",
    )
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex string


def test_different_times_produce_different_hashes():
    """Same coordinates but different acquisition times have distinct hashes."""
    h1 = _generate_observation_hash(
        source="VIIRS_NOAA20_NRT",
        latitude=34.0522,
        longitude=-118.2437,
        acq_date="2026-08-29",
        acq_time="1430",
        satellite="NOAA-20",
        instrument="VIIRS",
    )
    h2 = _generate_observation_hash(
        source="VIIRS_NOAA20_NRT",
        latitude=34.0522,
        longitude=-118.2437,
        acq_date="2026-08-29",
        acq_time="1845",
        satellite="NOAA-20",
        instrument="VIIRS",
    )
    assert h1 != h2


def test_different_satellites_produce_different_hashes():
    """Same location/time from different satellites (NOAA-20 vs NOAA-21) are distinct."""
    h1 = _generate_observation_hash(
        source="VIIRS_NOAA20_NRT",
        latitude=34.0522,
        longitude=-118.2437,
        acq_date="2026-08-29",
        acq_time="1430",
        satellite="NOAA-20",
        instrument="VIIRS",
    )
    h2 = _generate_observation_hash(
        source="VIIRS_NOAA21_NRT",
        latitude=34.0522,
        longitude=-118.2437,
        acq_date="2026-08-29",
        acq_time="1430",
        satellite="NOAA-21",
        instrument="VIIRS",
    )
    assert h1 != h2


def test_repeated_normalization_preserves_hash():
    """Normalizing identical raw rows results in identical observation_hash."""
    row = {
        "latitude": "12.3456",
        "longitude": "78.9012",
        "acq_date": "2026-08-29",
        "acq_time": "0600",
        "satellite": "N20",
        "instrument": "VIIRS",
    }
    obs1, _ = normalize_row(row, "VIIRS_NOAA20_NRT", 0)
    obs2, _ = normalize_row(row, "VIIRS_NOAA20_NRT", 1)

    assert obs1 is not None and obs2 is not None
    assert obs1.observation_hash == obs2.observation_hash
