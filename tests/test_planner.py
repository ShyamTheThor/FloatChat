"""
tests/test_planner.py
=====================
Unit tests for Pydantic QueryIntent schema validation.
"""

import pytest
from pydantic import ValidationError
from backend.schemas.query import QueryIntent, RegionBounds


def test_query_intent_valid():
    intent = QueryIntent(
        query_type="composite",
        parameter="salinity",
        visualization="depth_profile",
        region=RegionBounds(min_lat=5.0, max_lat=25.0, min_lon=55.0, max_lon=80.0, region_name="Arabian Sea"),
        min_depth=0.0,
        max_depth=200.0,
    )
    assert intent.parameter == "salinity"
    assert intent.visualization == "depth_profile"
    assert intent.region.min_lat == 5.0


def test_query_intent_invalid_lat_bounds():
    with pytest.raises(ValidationError):
        RegionBounds(min_lat=25.0, max_lat=5.0, min_lon=55.0, max_lon=80.0)


def test_query_intent_invalid_depth_bounds():
    with pytest.raises(ValidationError):
        QueryIntent(min_depth=500.0, max_depth=100.0)


def test_deterministic_planner_benchmark():
    """Verify that deterministic planner achieves >= 95% accuracy across representative queries."""
    from scripts.eval_planner import run_benchmark
    results = run_benchmark()
    assert results["overall_accuracy"] >= 95.0
    assert results["param_acc"] == 100.0
    assert results["region_acc"] == 100.0
