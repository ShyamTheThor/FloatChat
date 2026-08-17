"""
backend/queries.py
==================
Query functions for the argo_profiles table.
Provides unified, parameterized SQL retrieval with dataset metadata extraction.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psycopg2.extras

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.db import get_connection

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


def get_dataset_metadata(conn=None) -> dict[str, Any]:
    """
    Query PostgreSQL to determine dataset boundaries and statistics.
    Returns earliest/latest timestamps, observation count, unique float count,
    and spatial bounding box.
    """
    sql = """
        SELECT 
            MIN(timestamp) AS earliest_date,
            MAX(timestamp) AS latest_date,
            COUNT(*) AS total_observations,
            COUNT(DISTINCT float_id) AS total_floats,
            COUNT(DISTINCT (float_id || '_' || COALESCE(cycle_number::text, '0'))) AS total_profiles,
            MIN(lat) AS min_lat,
            MAX(lat) AS max_lat,
            MIN(lon) AS min_lon,
            MAX(lon) AS max_lon,
            MIN(depth_m) AS min_depth,
            MAX(depth_m) AS max_depth
        FROM argo_profiles;
    """
    _conn = conn or get_connection()
    try:
        with _conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            res = cur.fetchone()
            if res and res["total_observations"] > 0:
                return {
                    "earliest_date": str(res["earliest_date"])[:10] if res["earliest_date"] else None,
                    "latest_date": str(res["latest_date"])[:10] if res["latest_date"] else None,
                    "total_observations": int(res["total_observations"]),
                    "total_floats": int(res["total_floats"]),
                    "total_profiles": int(res["total_profiles"]),
                    "min_lat": float(res["min_lat"]) if res["min_lat"] is not None else None,
                    "max_lat": float(res["max_lat"]) if res["max_lat"] is not None else None,
                    "min_lon": float(res["min_lon"]) if res["min_lon"] is not None else None,
                    "max_lon": float(res["max_lon"]) if res["max_lon"] is not None else None,
                    "min_depth": float(res["min_depth"]) if res["min_depth"] is not None else None,
                    "max_depth": float(res["max_depth"]) if res["max_depth"] is not None else None,
                    "status": "online"
                }
            return {
                "earliest_date": None,
                "latest_date": None,
                "total_observations": 0,
                "total_floats": 0,
                "total_profiles": 0,
                "status": "empty"
            }
    finally:
        if conn is None:
            _conn.close()


def query_composite(
    min_lat: Optional[float] = None,
    max_lat: Optional[float] = None,
    min_lon: Optional[float] = None,
    max_lon: Optional[float] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_depth: Optional[float] = None,
    max_depth: Optional[float] = None,
    target_depth: Optional[float] = None,
    depth_tolerance: float = 15.0,
    parameter: str = "all",
    float_id: Optional[str] = None,
    limit: int = _RESULT_LIMIT,
    conn=None,
) -> list[dict[str, Any]]:
    """
    Execute a parameterized SQL query with dynamic WHERE clause matching
    any combination of region, date range, depth range, and parameter requirements.
    """
    conditions: List[str] = ["1=1"]
    params: Dict[str, Any] = {}

    if min_lat is not None and max_lat is not None:
        conditions.append("lat BETWEEN %(min_lat)s AND %(max_lat)s")
        params["min_lat"] = min_lat
        params["max_lat"] = max_lat

    if min_lon is not None and max_lon is not None:
        conditions.append("lon BETWEEN %(min_lon)s AND %(max_lon)s")
        params["min_lon"] = min_lon
        params["max_lon"] = max_lon

    if start_date:
        conditions.append("timestamp >= %(start_date)s::timestamptz")
        params["start_date"] = start_date

    if end_date:
        conditions.append("timestamp <= %(end_date)s::timestamptz + INTERVAL '1 day' - INTERVAL '1 second'")
        params["end_date"] = end_date

    if target_depth is not None:
        conditions.append("depth_m BETWEEN %(t_min)s AND %(t_max)s")
        params["t_min"] = max(0.0, target_depth - depth_tolerance)
        params["t_max"] = target_depth + depth_tolerance
    elif min_depth is not None or max_depth is not None:
        if min_depth is not None:
            conditions.append("depth_m >= %(min_depth)s")
            params["min_depth"] = min_depth
        if max_depth is not None:
            conditions.append("depth_m <= %(max_depth)s")
            params["max_depth"] = max_depth

    if parameter == "temperature":
        conditions.append("temperature IS NOT NULL")
    elif parameter == "salinity":
        conditions.append("salinity IS NOT NULL")
    elif parameter == "pressure":
        conditions.append("pressure_dbar IS NOT NULL")

    if float_id:
        conditions.append("float_id = %(float_id)s")
        params["float_id"] = float_id

    where_clause = " AND ".join(conditions)
    sql = f"""
        SELECT {_SELECT_COLS}
        FROM argo_profiles
        WHERE {where_clause}
        ORDER BY timestamp DESC, float_id, depth_m ASC
        LIMIT {limit};
    """

    _conn = conn or get_connection()
    try:
        with _conn.cursor() as cur:
            cur.execute(sql, params)
            rows = _rows_to_dicts(cur.fetchall(), cur.description)
    finally:
        if conn is None:
            _conn.close()

    _warn_if_capped(rows, limit, "query_composite")
    return rows


# ── Backward-compatible convenience functions ─────────────────────────────────

def query_by_region(
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
    conn=None,
) -> list[dict[str, Any]]:
    return query_composite(min_lat=min_lat, max_lat=max_lat, min_lon=min_lon, max_lon=max_lon, conn=conn)


def query_by_date_range(
    start_date: str,
    end_date: str,
    conn=None,
) -> list[dict[str, Any]]:
    return query_composite(start_date=start_date, end_date=end_date, conn=conn)


def query_by_depth_band(
    min_depth: float,
    max_depth: float,
    conn=None,
) -> list[dict[str, Any]]:
    return query_composite(min_depth=min_depth, max_depth=max_depth, conn=conn)


if __name__ == "__main__":
    print("Testing get_dataset_metadata()...")
    try:
        meta = get_dataset_metadata()
        print("Metadata:", meta)
    except Exception as e:
        print("Error fetching metadata:", e)

