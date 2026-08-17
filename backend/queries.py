"""
backend/queries.py
==================
Query functions for the argo_profiles table.

These are the primary interface for the AI/ML / RAG layer.
All functions return a list of dicts — simple to iterate in Python,
easy to convert to a DataFrame if needed.

Function signatures are intentionally simple:
  - string dates in ISO-8601 format ("YYYY-MM-DD" or full ISO-8601)
  - float degrees for lat/lon
  - float metres for depth

All queries include a LIMIT 10_000 safety cap to prevent runaway results;
a warning is printed if the cap is hit.

Usage example
-------------
  from backend.queries import query_by_region, query_by_date_range, query_by_depth_band

  rows = query_by_region(min_lat=5.0, max_lat=25.0, min_lon=60.0, max_lon=90.0)
  df   = pd.DataFrame(rows)   # optional — works great with pandas
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import psycopg2.extras

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.db import get_connection

# ── Shared helpers ─────────────────────────────────────────────────────────────

_RESULT_LIMIT = 10_000

_SELECT_COLS = """
    id, float_id, cycle_number,
    lat, lon, timestamp,
    pressure_dbar, depth_m,
    temperature, salinity,
    basin, profile_direction, data_mode
"""


def _rows_to_dicts(cursor_results: list[Any], description) -> list[dict[str, Any]]:
    """Convert psycopg2 cursor results to list of dicts."""
    cols = [desc[0] for desc in description]
    return [dict(zip(cols, row)) for row in cursor_results]


def _warn_if_capped(rows: list[dict], limit: int, query_name: str) -> None:
    if len(rows) >= limit:
        print(
            f"[queries.py] WARNING: {query_name} hit the {limit:,}-row limit. "
            "Results are truncated — narrow your query parameters.",
            file=sys.stderr,
        )


# ── Public query functions ─────────────────────────────────────────────────────

def query_by_region(
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
    conn=None,
) -> list[dict[str, Any]]:
    """
    Return all observation rows within a lat/lon bounding box.

    Parameters
    ----------
    min_lat, max_lat : float
        Latitude bounds in decimal degrees (−90 to +90).
    min_lon, max_lon : float
        Longitude bounds in decimal degrees (−180 to +180).

    Returns
    -------
    list[dict]
        Each dict has keys: id, float_id, cycle_number, lat, lon, timestamp,
        pressure_dbar, depth_m, temperature, salinity, basin,
        profile_direction, data_mode.

    Example
    -------
    >>> rows = query_by_region(5.0, 25.0, 60.0, 90.0)
    >>> print(f"{len(rows)} rows in Arabian Sea box")
    """
    sql = f"""
        SELECT {_SELECT_COLS}
        FROM   argo_profiles
        WHERE  lat BETWEEN %(min_lat)s AND %(max_lat)s
          AND  lon BETWEEN %(min_lon)s AND %(max_lon)s
        ORDER  BY timestamp DESC, float_id, pressure_dbar
        LIMIT  {_RESULT_LIMIT};
    """
    params = dict(min_lat=min_lat, max_lat=max_lat, min_lon=min_lon, max_lon=max_lon)

    _conn = conn or get_connection()
    try:
        with _conn.cursor() as cur:
            cur.execute(sql, params)
            rows = _rows_to_dicts(cur.fetchall(), cur.description)
    finally:
        if conn is None:
            _conn.close()

    _warn_if_capped(rows, _RESULT_LIMIT, "query_by_region")
    return rows


def query_by_date_range(
    start_date: str,
    end_date: str,
    conn=None,
) -> list[dict[str, Any]]:
    """
    Return all observation rows with timestamp in [start_date, end_date].

    Parameters
    ----------
    start_date, end_date : str
        ISO-8601 date or datetime strings.
        Examples: "2023-01-01", "2023-01-01T00:00:00Z"
        The range is inclusive on both ends.

    Returns
    -------
    list[dict]
        Same structure as query_by_region.

    Example
    -------
    >>> rows = query_by_date_range("2023-01-01", "2023-01-07")
    >>> print(f"{len(rows)} rows in first week of Jan 2023")
    """
    sql = f"""
        SELECT {_SELECT_COLS}
        FROM   argo_profiles
        WHERE  timestamp BETWEEN %(start_date)s::timestamptz
                              AND %(end_date)s::timestamptz + INTERVAL '1 day' - INTERVAL '1 second'
        ORDER  BY timestamp DESC, float_id, pressure_dbar
        LIMIT  {_RESULT_LIMIT};
    """
    params = dict(start_date=start_date, end_date=end_date)

    _conn = conn or get_connection()
    try:
        with _conn.cursor() as cur:
            cur.execute(sql, params)
            rows = _rows_to_dicts(cur.fetchall(), cur.description)
    finally:
        if conn is None:
            _conn.close()

    _warn_if_capped(rows, _RESULT_LIMIT, "query_by_date_range")
    return rows


def query_by_depth_band(
    min_depth: float,
    max_depth: float,
    conn=None,
) -> list[dict[str, Any]]:
    """
    Return all observation rows within a depth band [min_depth, max_depth] metres.

    Parameters
    ----------
    min_depth, max_depth : float
        Depth bounds in metres (positive downward).
        Examples: query_by_depth_band(0, 200) for the upper mixed layer.

    Returns
    -------
    list[dict]
        Same structure as query_by_region.

    Example
    -------
    >>> rows = query_by_depth_band(0, 200)
    >>> print(f"{len(rows)} rows in the upper 200 m")
    """
    sql = f"""
        SELECT {_SELECT_COLS}
        FROM   argo_profiles
        WHERE  depth_m IS NOT NULL
          AND  depth_m BETWEEN %(min_depth)s AND %(max_depth)s
        ORDER  BY depth_m, timestamp DESC, float_id
        LIMIT  {_RESULT_LIMIT};
    """
    params = dict(min_depth=min_depth, max_depth=max_depth)

    _conn = conn or get_connection()
    try:
        with _conn.cursor() as cur:
            cur.execute(sql, params)
            rows = _rows_to_dicts(cur.fetchall(), cur.description)
    finally:
        if conn is None:
            _conn.close()

    _warn_if_capped(rows, _RESULT_LIMIT, "query_by_depth_band")
    return rows


# ── Quick demo / smoke test ────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("FloatChat — Query Demo")
    print("=" * 60)

    # 1. Region query: Arabian Sea
    print("\n[1] query_by_region — Arabian Sea (lat 5–25, lon 55–80):")
    rows = query_by_region(5.0, 25.0, 55.0, 80.0)
    print(f"    → {len(rows)} rows")
    if rows:
        r = rows[0]
        print(f"    Sample: float_id={r['float_id']} cycle={r['cycle_number']} "
              f"lat={r['lat']:.3f} lon={r['lon']:.3f} "
              f"depth={r['depth_m']}m temp={r['temperature']}°C "
              f"sal={r['salinity']}psu ts={r['timestamp']}")

    # 2. Date range query
    print("\n[2] query_by_date_range — 2023-01-01 to 2023-01-07:")
    rows = query_by_date_range("2023-01-01", "2023-01-07")
    print(f"    → {len(rows)} rows")
    if rows:
        r = rows[0]
        print(f"    Sample: float_id={r['float_id']} ts={r['timestamp']} "
              f"temp={r['temperature']}°C sal={r['salinity']}psu")

    # 3. Depth band query: upper mixed layer
    print("\n[3] query_by_depth_band — 0 to 200 m (upper mixed layer):")
    rows = query_by_depth_band(0.0, 200.0)
    print(f"    → {len(rows)} rows")
    if rows:
        r = rows[0]
        print(f"    Sample: float_id={r['float_id']} depth={r['depth_m']}m "
              f"temp={r['temperature']}°C sal={r['salinity']}psu")

    print("\n✓ All three query functions ran successfully.\n")
