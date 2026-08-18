"""
tests/test_stress.py
====================
Production-readiness, security, and adversarial stress tests for FloatChat.
Verifies query planner robustness, data correctness, SQL safety, analytics resilience,
and error handling edge cases.
"""

import pytest
from pydantic import ValidationError

from backend.schemas.query import QueryIntent, RegionBounds, AnalyticsSummary
from backend.services.analytics import compute_analytics
from backend.parser import _pressure_to_depth, parse_argovis_profile
from backend.validate import validate_rows, null_summary
from backend.queries import query_composite, _SELECT_COLS


# ==============================================================================
# 1. BREAK THE QUERY PLANNER — Adversarial & Malformed Inputs
# ==============================================================================

def test_adversarial_date_sql_injection():
    """Verify SQL injection strings in date fields are rejected by format validator."""
    with pytest.raises(ValidationError):
        QueryIntent(start_date="2023-01-01'; DROP TABLE argo_profiles; --")


def test_adversarial_inverted_dates():
    """Verify chronological sanity: start_date > end_date is rejected."""
    with pytest.raises(ValidationError):
        QueryIntent(start_date="2024-06-01", end_date="2023-01-01")


def test_adversarial_invalid_calendar_dates():
    """Verify non-existent calendar dates (e.g. Feb 30) are rejected."""
    with pytest.raises(ValidationError):
        QueryIntent(start_date="2023-02-30")

    with pytest.raises(ValidationError):
        QueryIntent(start_date="not-a-date")


def test_adversarial_inverted_latitudes():
    """Verify min_lat > max_lat is rejected."""
    with pytest.raises(ValidationError):
        RegionBounds(min_lat=25.0, max_lat=5.0, min_lon=55.0, max_lon=80.0)


def test_adversarial_out_of_bounds_lat_lon():
    """Verify latitude beyond [-90, 90] and longitude beyond [-180, 180] are rejected."""
    with pytest.raises(ValidationError):
        RegionBounds(min_lat=-95.0, max_lat=25.0, min_lon=55.0, max_lon=80.0)

    with pytest.raises(ValidationError):
        RegionBounds(min_lat=5.0, max_lat=25.0, min_lon=-200.0, max_lon=80.0)


def test_adversarial_inverted_depth():
    """Verify min_depth > max_depth is rejected."""
    with pytest.raises(ValidationError):
        QueryIntent(min_depth=1000.0, max_depth=100.0)


def test_adversarial_negative_depth():
    """Verify negative depth is rejected."""
    with pytest.raises(ValidationError):
        QueryIntent(min_depth=-50.0)


def test_adversarial_unsupported_parameter():
    """Verify unsupported physical parameters (e.g. uranium, radiation) are rejected."""
    with pytest.raises(ValidationError):
        QueryIntent(parameter="radiation")


def test_adversarial_unsupported_visualization():
    """Verify unsupported visualization types are rejected."""
    with pytest.raises(ValidationError):
        QueryIntent(visualization="3d_voxel")


# ==============================================================================
# 2. DATA & SCIENTIFIC CORRECTNESS — Pressure, Units, Nulls
# ==============================================================================

def test_negative_pressure_handling():
    """Verify negative pressure never produces a fake depth=0 measurement."""
    assert _pressure_to_depth(-10.0, 15.0) is None
    assert _pressure_to_depth(None, 15.0) is None
    assert _pressure_to_depth(0.0, 15.0) == 0.0


def test_parser_corrupted_payload():
    """Verify malformed profile payloads (missing coords, broken data arrays) fail safely."""
    # Profile with missing geolocation
    p1 = {"_id": "9999999_001", "timestamp": "2023-01-01T00:00:00Z", "data": [[25.0], [35.0], [10.0]]}
    assert parse_argovis_profile(p1) == []

    # Profile with missing timestamp
    p2 = {"_id": "9999999_001", "geolocation": {"coordinates": [65.0, 15.0]}, "data": [[25.0], [35.0], [10.0]]}
    assert parse_argovis_profile(p2) == []

    # Profile with empty coordinates
    p3 = {"_id": "9999999_001", "geolocation": {"coordinates": []}, "timestamp": "2023-01-01T00:00:00Z"}
    assert parse_argovis_profile(p3) == []


def test_validation_extreme_and_null_values():
    """Verify physical range checking correctly separates valid from out-of-range observations."""
    test_rows = [
        # Valid observation
        {"temperature": 26.5, "salinity": 35.8, "pressure_dbar": 50.0, "lat": 15.0, "lon": 65.0},
        # Out-of-range temperature (> 35 °C)
        {"temperature": 45.0, "salinity": 35.8, "pressure_dbar": 50.0, "lat": 15.0, "lon": 65.0},
        # Out-of-range salinity (> 42 psu)
        {"temperature": 26.5, "salinity": 55.0, "pressure_dbar": 50.0, "lat": 15.0, "lon": 65.0},
        # Observation with NULL measurement (sensor gap)
        {"temperature": None, "salinity": 35.8, "pressure_dbar": 50.0, "lat": 15.0, "lon": 65.0},
    ]

    valid, flagged = validate_rows(test_rows)
    assert len(valid) == 2  # 1st and 4th rows (NULLs are preserved, not flagged as range errors)
    assert len(flagged) == 2  # 2nd and 3rd rows

    null_stats = null_summary(valid)
    assert null_stats["temperature"] == 1
    assert null_stats["salinity"] == 0


# ==============================================================================
# 3. ANALYTICS ENGINE STRESS TESTS — Edge Cases
# ==============================================================================

def test_analytics_empty_dataset():
    """Verify analytics engine returns a clean empty summary without crashing."""
    res = compute_analytics([])
    assert res.observation_count == 0
    assert res.float_count == 0
    assert res.temp_mean is None
    assert res.sal_mean is None


def test_analytics_all_null_measurements():
    """Verify dataset with valid coords but all-null measurements handles numpy aggregates safely."""
    rows = [
        {"float_id": "2902275", "cycle_number": 1, "timestamp": "2023-01-01T00:00:00Z", "temperature": None, "salinity": None, "depth_m": None},
        {"float_id": "2902275", "cycle_number": 1, "timestamp": "2023-01-01T00:00:00Z", "temperature": None, "salinity": None, "depth_m": None},
    ]
    res = compute_analytics(rows)
    assert res.observation_count == 2
    assert res.float_count == 1
    assert res.temp_mean is None
    assert res.sal_mean is None
    assert res.depth_min is None


def test_analytics_statistical_correctness():
    """Verify mathematical correctness of min, max, mean and profile count."""
    rows = [
        {"float_id": "F1", "cycle_number": 1, "timestamp": "2023-01-01T00:00:00Z", "temperature": 20.0, "salinity": 35.0, "depth_m": 10.0},
        {"float_id": "F1", "cycle_number": 1, "timestamp": "2023-01-01T00:00:00Z", "temperature": 30.0, "salinity": 37.0, "depth_m": 100.0},
        {"float_id": "F2", "cycle_number": 1, "timestamp": "2023-01-05T00:00:00Z", "temperature": 25.0, "salinity": 36.0, "depth_m": 50.0},
    ]
    res = compute_analytics(rows)
    assert res.observation_count == 3
    assert res.float_count == 2
    assert res.profile_count == 2
    assert res.temp_min == 20.0
    assert res.temp_max == 30.0
    assert res.temp_mean == 25.0
    assert res.sal_min == 35.0
    assert res.sal_max == 37.0
    assert res.sal_mean == 36.0
    assert res.depth_min == 10.0
    assert res.depth_max == 100.0
    assert res.earliest_date == "2023-01-01"
    assert res.latest_date == "2023-01-05"
