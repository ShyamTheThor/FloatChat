"""
tests/test_validate.py
======================
Unit tests for physical range validation rules.
"""

from backend.validate import validate_rows, null_summary


def test_validate_rows_valid():
    rows = [
        {"temperature": 25.0, "salinity": 35.5, "pressure_dbar": 100.0, "lat": 15.0, "lon": 65.0},
        {"temperature": 12.0, "salinity": 34.8, "pressure_dbar": 500.0, "lat": -5.0, "lon": 75.0},
    ]
    valid, flagged = validate_rows(rows)
    assert len(valid) == 2
    assert len(flagged) == 0


def test_validate_rows_flagged():
    rows = [
        # Out of range temperature (99.0 C)
        {"temperature": 99.0, "salinity": 35.5, "pressure_dbar": 100.0, "lat": 15.0, "lon": 65.0},
        # Out of range latitude (150.0)
        {"temperature": 20.0, "salinity": 35.5, "pressure_dbar": 100.0, "lat": 150.0, "lon": 65.0},
    ]
    valid, flagged = validate_rows(rows)
    assert len(valid) == 0
    assert len(flagged) == 2
    assert "_validation_errors" in flagged[0]


def test_null_summary():
    rows = [
        {"temperature": 25.0, "salinity": None, "pressure_dbar": 10.0},
        {"temperature": None, "salinity": 35.0, "pressure_dbar": 20.0},
    ]
    summary = null_summary(rows)
    assert summary["temperature"] == 1
    assert summary["salinity"] == 1
    assert summary["pressure_dbar"] == 0
    assert summary["total_rows"] == 2
