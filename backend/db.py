"""
backend/db.py
=============
PostgreSQL connection handling and schema management.

Environment variables (loaded from .env):
  POSTGRES_HOST      default: localhost
  POSTGRES_PORT      default: 5432
  POSTGRES_USER      default: floatchat
  POSTGRES_PASSWORD  default: floatchat_dev
  POSTGRES_DB        default: argo
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# ── Connection ────────────────────────────────────────────────────────────────

def get_connection() -> psycopg2.extensions.connection:
    """Return a psycopg2 connection using .env credentials."""
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "floatchat"),
        password=os.getenv("POSTGRES_PASSWORD", "floatchat_dev"),
        dbname=os.getenv("POSTGRES_DB", "argo"),
        connect_timeout=10,
    )


# ── Schema management ─────────────────────────────────────────────────────────

def create_tables(conn: psycopg2.extensions.connection | None = None) -> None:
    """Create the argo_profiles table and indexes (idempotent)."""
    sql_path = Path(__file__).parent / "create_tables.sql"
    ddl = sql_path.read_text()

    _conn = conn or get_connection()
    try:
        with _conn.cursor() as cur:
            cur.execute(ddl)
        _conn.commit()
        print("✓ Tables and indexes ready.")
    finally:
        if conn is None:
            _conn.close()


# ── Bulk upsert ───────────────────────────────────────────────────────────────

_UPSERT_SQL = """
INSERT INTO argo_profiles (
    float_id, cycle_number, lat, lon, timestamp,
    pressure_dbar, depth_m, temperature, salinity,
    basin, profile_direction, data_mode, source_url
) VALUES (
    %(float_id)s, %(cycle_number)s, %(lat)s, %(lon)s, %(timestamp)s,
    %(pressure_dbar)s, %(depth_m)s, %(temperature)s, %(salinity)s,
    %(basin)s, %(profile_direction)s, %(data_mode)s, %(source_url)s
)
ON CONFLICT (float_id, COALESCE(cycle_number, -1), COALESCE(pressure_dbar, -1.0)) DO NOTHING;
"""



def upsert_profiles(
    rows: list[dict[str, Any]],
    conn: psycopg2.extensions.connection | None = None,
    batch_size: int = 1000,
) -> int:
    """
    Bulk-upsert parsed profile rows into argo_profiles.

    Uses ON CONFLICT DO NOTHING so the function is safe to call repeatedly
    (re-running the ETL will not duplicate rows).

    Returns the number of rows actually inserted (≤ len(rows)).
    """
    if not rows:
        return 0

    _conn = conn or get_connection()
    inserted = 0
    try:
        with _conn.cursor() as cur:
            for start in range(0, len(rows), batch_size):
                batch = rows[start : start + batch_size]
                psycopg2.extras.execute_batch(cur, _UPSERT_SQL, batch, page_size=batch_size)
                inserted += cur.rowcount
        _conn.commit()
    finally:
        if conn is None:
            _conn.close()

    return inserted


# ── Sanity checks ─────────────────────────────────────────────────────────────

def row_count(conn: psycopg2.extensions.connection | None = None) -> int:
    """Return current row count in argo_profiles."""
    _conn = conn or get_connection()
    try:
        with _conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM argo_profiles;")
            return cur.fetchone()[0]
    finally:
        if conn is None:
            _conn.close()


if __name__ == "__main__":
    # Quick connectivity test
    try:
        conn = get_connection()
        print("✓ Connected to PostgreSQL")
        conn.close()
    except Exception as e:
        print(f"✗ Connection failed: {e}")
