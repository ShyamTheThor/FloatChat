"""
tests/test_parser.py
====================
Unit tests for ARGO parser and Leroy & Parthiot depth conversion.
"""

from backend.parser import parse_argovis_profile, _pressure_to_depth, _parse_id


def test_pressure_to_depth():
    # At 0 pressure, depth is 0
    assert _pressure_to_depth(0.0, 15.0) == 0.0

    # At 100 dbar pressure near equator (0 deg lat), depth approx ~99.27m
    d0 = _pressure_to_depth(100.0, 0.0)
    assert 98.0 <= d0 <= 101.0

    # Higher latitude correction increases depth slightly
    d45 = _pressure_to_depth(100.0, 45.0)
    assert d45 > d0


def test_id_parsing():
    assert _parse_id("2902275_239") == ("2902275", 239)
    assert _parse_id("1902345") == ("1902345", None)



def test_parse_argovis_profile_valid():
    sample_profile = {
        "_id": "2902275_001",
        "geolocation": {"coordinates": [65.0, 15.0]},
        "timestamp": "2023-01-01T12:00:00Z",
        "basin": 3,
        "data_info": [["temperature", "salinity", "pressure"]],
        "data": [
            [28.5, 27.8],  # temp
            [36.2, 36.5],  # sal
            [10.0, 50.0]   # pres
        ]
    }

    rows = parse_argovis_profile(sample_profile)
    assert len(rows) == 2
    r0 = rows[0]
    assert r0["float_id"] == "2902275"
    assert r0["cycle_number"] == 1
    assert r0["lat"] == 15.0
    assert r0["lon"] == 65.0
    assert r0["pressure_dbar"] == 10.0
    assert r0["temperature"] == 28.5
    assert r0["salinity"] == 36.2
    assert r0["depth_m"] > 0


def test_parse_argovis_profile_missing_coords():
    incomplete_profile = {
        "_id": "2902275_002",
        "timestamp": "2023-01-01T12:00:00Z",
        "data": [[25.0], [35.0], [10.0]]
    }
    rows = parse_argovis_profile(incomplete_profile)
    assert len(rows) == 0
