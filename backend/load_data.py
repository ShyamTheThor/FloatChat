"""
backend/load_data.py
====================
ETL entry point: reads raw Argovis JSON files, parses them, validates them,
and loads results into PostgreSQL.

Usage
-----
  python -m backend.load_data [--data-dir data/raw] [--drop-flagged]

Flags
-----
  --data-dir       Directory containing argovis_*.json files (default: data/raw)
  --drop-flagged   If set, flagged (out-of-range) rows are NOT loaded.
                   Default: flagged rows ARE loaded (they just get logged).
  --dry-run        Parse and validate without touching the database.

Re-run safety
-------------
Uses ON CONFLICT DO NOTHING → safe to re-run at any time without duplicates.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as  python -m backend.load_data  from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.db       import create_tables, get_connection, upsert_profiles, row_count
from backend.parser   import parse_argovis_profile
from backend.validate import null_summary, print_validation_report, validate_rows


# ── ETL ───────────────────────────────────────────────────────────────────────

def load_file(
    path: Path,
    drop_flagged: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Process one JSON file: parse → validate → upsert.

    Returns a stats dict with keys:
      profiles_in_file, rows_parsed, rows_valid, rows_flagged, rows_inserted
    """
    print(f"\n{'─'*60}")
    print(f"Processing: {path.name}")

    raw_profiles: list[dict] = json.loads(path.read_text())
    print(f"  Profiles in file : {len(raw_profiles)}")

    # Parse all profiles into flat rows
    all_rows: list[dict] = []
    skipped_profiles = 0
    for prof in raw_profiles:
        rows = parse_argovis_profile(prof)
        if not rows:
            skipped_profiles += 1
        all_rows.extend(rows)

    print(f"  Profiles skipped : {skipped_profiles}  (missing lat/lon/timestamp)")
    print(f"  Rows parsed      : {len(all_rows):,}")

    # Validate
    valid_rows, flagged_rows = validate_rows(all_rows)
    null_counts = null_summary(valid_rows)
    print_validation_report(valid_rows, flagged_rows, null_counts)

    # Decide what to load
    rows_to_load = valid_rows if drop_flagged else all_rows
    # Strip internal _validation_errors key before DB insert
    for row in rows_to_load:
        row.pop("_validation_errors", None)

    # Insert
    inserted = 0
    if not dry_run:
        inserted = upsert_profiles(rows_to_load)
        print(f"  Rows inserted    : {inserted:,}  (ON CONFLICT DO NOTHING)")
    else:
        print("  [dry-run] skipping DB insert")

    return {
        "profiles_in_file": len(raw_profiles),
        "rows_parsed":      len(all_rows),
        "rows_valid":       len(valid_rows),
        "rows_flagged":     len(flagged_rows),
        "rows_inserted":    inserted,
    }


def run_etl(
    data_dir: Path,
    drop_flagged: bool = False,
    dry_run: bool = False,
) -> None:
    """Scan data_dir for argovis_*.json files and load each one."""

    files = sorted(data_dir.glob("argovis_*.json"))
    if not files:
        print(f"\n[!] No argovis_*.json files found in {data_dir}/")
        print("    Run: python scripts/fetch_sample_data.py  first.")
        sys.exit(1)

    print(f"\n{'═'*60}")
    print(f"FloatChat ETL — loading {len(files)} file(s) from {data_dir}/")
    print(f"  drop_flagged={drop_flagged}  dry_run={dry_run}")
    print(f"{'═'*60}")

    # Create schema (idempotent)
    if not dry_run:
        create_tables()

    # Process each file
    totals = {
        "profiles_in_file": 0,
        "rows_parsed":      0,
        "rows_valid":       0,
        "rows_flagged":     0,
        "rows_inserted":    0,
    }
    for path in files:
        stats = load_file(path, drop_flagged=drop_flagged, dry_run=dry_run)
        for k in totals:
            totals[k] += stats[k]

    # Final summary
    print(f"\n{'═'*60}")
    print("ETL COMPLETE")
    print(f"{'═'*60}")
    print(f"  Files processed  : {len(files)}")
    print(f"  Total profiles   : {totals['profiles_in_file']:,}")
    print(f"  Total rows parsed: {totals['rows_parsed']:,}")
    print(f"  Rows flagged     : {totals['rows_flagged']:,}")
    print(f"  Rows inserted    : {totals['rows_inserted']:,}")

    # Row count sanity check
    if not dry_run:
        db_count = row_count()
        print(f"\n  DB row count (argo_profiles): {db_count:,}")
        if db_count == 0:
            print("  [!] WARNING: DB row count is 0 — check DB connection and logs above.")
        else:
            print("  ✓ Sanity check passed: DB has data.")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="FloatChat ETL — load ARGO data into PostgreSQL")
    parser.add_argument("--data-dir",    type=str,  default="data/raw",
                        help="Directory of argovis_*.json files (default: data/raw)")
    parser.add_argument("--drop-flagged", action="store_true",
                        help="Exclude out-of-range rows from DB load")
    parser.add_argument("--dry-run",     action="store_true",
                        help="Parse and validate without writing to DB")
    args = parser.parse_args()

    run_etl(
        data_dir=Path(args.data_dir),
        drop_flagged=args.drop_flagged,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
