"""
Unit tests for observation normalization and validation.
"""

import pytest
from app.services.observation_normalizer import normalize_row, normalize_rows


def test_valid_noaa20_observation():
    row = {
        "latitude": "37.7749",
        "longitude": "-122.4194",
        "bright_ti4": "325.5",
        "bright_ti5": "290.1",
        "scan": "0.39",
        "track": "0.36",
        "acq_date": "2026-08-29",
        "acq_time": "1430",
        "satellite": "N20",
        "instrument": "VIIRS",
        "confidence": "nominal",
        "version": "2.0NRT",
        "frp": "12.4",
        "daynight": "D",
    }
    obs, err = normalize_row(row, "VIIRS_NOAA20_NRT", 0)

    assert err is None
    assert obs is not None
    assert obs.source == "VIIRS_NOAA20_NRT"
    assert obs.latitude == 37.7749
    assert obs.longitude == -122.4194
    assert obs.bright_ti4 == 325.5
    assert obs.bright_ti5 == 290.1
    assert obs.brightness == 325.5
    assert obs.frp == 12.4
    assert obs.confidence == "nominal"
    assert obs.daynight == "D"
    assert obs.satellite == "N20"
    assert obs.instrument == "VIIRS"
    assert obs.acq_date == "2026-08-29"
    assert obs.acq_time == "1430"
    assert obs.acquisition_datetime.year == 2026
    assert obs.acquisition_datetime.hour == 14
    assert obs.acquisition_datetime.minute == 30
    assert obs.observation_hash != ""
    assert "version" in obs.raw_data


def test_valid_noaa21_observation():
    row = {
        "latitude": "-23.5505",
        "longitude": "-46.6333",
        "bright_ti4": "340.2",
        "bright_ti5": "295.0",
        "acq_date": "2026-08-28",
        "acq_time": "0315",
        "satellite": "NOAA-21",
        "instrument": "VIIRS",
        "confidence": "high",
        "frp": "45.0",
        "daynight": "N",
    }
    obs, err = normalize_row(row, "VIIRS_NOAA21_NRT", 0)

    assert err is None
    assert obs is not None
    assert obs.source == "VIIRS_NOAA21_NRT"
    assert obs.latitude == -23.5505
    assert obs.longitude == -46.6333
    assert obs.daynight == "N"
    assert obs.confidence == "high"


def test_missing_optional_fields():
    row = {
        "latitude": "10.0",
        "longitude": "20.0",
        "acq_date": "2026-08-29",
        "acq_time": "1200",
    }
    obs, err = normalize_row(row, "VIIRS_NOAA20_NRT", 0)

    assert err is None
    assert obs is not None
    assert obs.latitude == 10.0
    assert obs.longitude == 20.0
    assert obs.brightness is None
    assert obs.frp is None
    assert obs.confidence is None
    assert obs.satellite == "Unknown"
    assert obs.instrument == "VIIRS"


def test_invalid_latitude():
    row = {
        "latitude": "95.0",  # Out of range [-90, 90]
        "longitude": "20.0",
        "acq_date": "2026-08-29",
        "acq_time": "1200",
    }
    obs, err = normalize_row(row, "VIIRS_NOAA20_NRT", 0)

    assert obs is None
    assert err is not None
    assert err.field == "latitude"


def test_invalid_longitude():
    row = {
        "latitude": "10.0",
        "longitude": "-190.0",  # Out of range [-180, 180]
        "acq_date": "2026-08-29",
        "acq_time": "1200",
    }
    obs, err = normalize_row(row, "VIIRS_NOAA20_NRT", 0)

    assert obs is None
    assert err is not None
    assert err.field == "longitude"


def test_invalid_acquisition_time():
    row = {
        "latitude": "10.0",
        "longitude": "20.0",
        "acq_date": "2026-08-29",
        "acq_time": "9999",  # Invalid hour/minute
    }
    obs, err = normalize_row(row, "VIIRS_NOAA20_NRT", 0)

    assert obs is None
    assert err is not None
    assert err.field == "acquisition_datetime"


def test_empty_frp_handled_as_none():
    row = {
        "latitude": "10.0",
        "longitude": "20.0",
        "acq_date": "2026-08-29",
        "acq_time": "1200",
        "frp": "   ",
    }
    obs, err = normalize_row(row, "VIIRS_NOAA20_NRT", 0)

    assert err is None
    assert obs is not None
    assert obs.frp is None


def test_batch_normalization():
    rows = [
        {
            "latitude": "10.0",
            "longitude": "20.0",
            "acq_date": "2026-08-29",
            "acq_time": "1200",
        },
        {
            "latitude": "invalid",
            "longitude": "20.0",
            "acq_date": "2026-08-29",
            "acq_time": "1200",
        },
        {
            "latitude": "30.0",
            "longitude": "40.0",
            "acq_date": "2026-08-29",
            "acq_time": "1300",
        },
    ]
    valid, errors = normalize_rows(rows, "VIIRS_NOAA20_NRT")

    assert len(valid) == 2
    assert len(errors) == 1
    assert errors[0].row_index == 1
