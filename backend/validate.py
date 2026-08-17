"""
backend/validate.py
===================
Physical range validation for parsed ARGO profile rows.

Validation rules (thresholds from docs/schema.md):
  temperature   : −2.0 … 35.0 °C
  salinity      : 0.0  … 42.0 psu
  pressure_dbar : 0    … 7000 dbar
  lat           : −90  … 90
  lon           : −180 … 180

Design decisions
----------------
- Rows are FLAGGED (not dropped).  The caller (load_data.py) decides
  what to do: by default, flagged rows are still loaded into the DB
  but a warning is printed.
- NULL values in temperature/salinity are NOT flagged as range errors —
  they are counted separately as null_count.
- This module is stateless: call validate_rows() with any list of dicts.
"""

from __future__ import annotations

from typing import Any


# ── Thresholds ─────────────────────────────────────────────────────────────────

TEMP_MIN   = -2.0
TEMP_MAX   = 35.0
SAL_MIN    =  0.0
SAL_MAX    = 42.0
PRES_MIN   =  0.0
PRES_MAX   = 7000.0
LAT_MIN    = -90.0
LAT_MAX    =  90.0
LON_MIN    = -180.0
LON_MAX    =  180.0


# ── Validation logic ───────────────────────────────────────────────────────────

def _check_row(row: dict[str, Any]) -> list[str]:
    """Return a list of violation messages for a single row (empty = valid)."""
    issues: list[str] = []

    temp = row.get("temperature")
    sal  = row.get("salinity")
    pres = row.get("pressure_dbar")
    lat  = row.get("lat")
    lon  = row.get("lon")

    if temp is not None and not (TEMP_MIN <= temp <= TEMP_MAX):
        issues.append(f"temperature={temp} outside [{TEMP_MIN}, {TEMP_MAX}]°C")

    if sal is not None and not (SAL_MIN <= sal <= SAL_MAX):
        issues.append(f"salinity={sal} outside [{SAL_MIN}, {SAL_MAX}] psu")

    if pres is not None and not (PRES_MIN <= pres <= PRES_MAX):
        issues.append(f"pressure_dbar={pres} outside [{PRES_MIN}, {PRES_MAX}]")

    if lat is not None and not (LAT_MIN <= lat <= LAT_MAX):
        issues.append(f"lat={lat} outside [{LAT_MIN}, {LAT_MAX}]")

    if lon is not None and not (LON_MIN <= lon <= LON_MAX):
        issues.append(f"lon={lon} outside [{LON_MIN}, {LON_MAX}]")

    return issues


def validate_rows(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Split rows into (valid_rows, flagged_rows).

    Each entry in flagged_rows has an extra key '_validation_errors'
    containing a list of violation message strings.

    Parameters
    ----------
    rows : list[dict]
        Parsed profile rows from parser.parse_argovis_file().

    Returns
    -------
    valid_rows   : rows that pass all checks
    flagged_rows : rows with at least one range violation
    """
    valid:   list[dict[str, Any]] = []
    flagged: list[dict[str, Any]] = []

    for row in rows:
        issues = _check_row(row)
        if issues:
            flagged_row = dict(row)
            flagged_row["_validation_errors"] = issues
            flagged.append(flagged_row)
        else:
            valid.append(row)

    return valid, flagged


def null_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    """
    Count NULL values for the three core measurement columns.

    Returns a dict like:
      {"temperature": 42, "salinity": 7, "pressure_dbar": 0, "total_rows": 1234}
    """
    counts = {"temperature": 0, "salinity": 0, "pressure_dbar": 0}
    for row in rows:
        for field in counts:
            if row.get(field) is None:
                counts[field] += 1
    counts["total_rows"] = len(rows)
    return counts


def print_validation_report(
    valid: list[dict],
    flagged: list[dict],
    null_counts: dict[str, int],
) -> None:
    """Print a human-readable validation summary to stdout."""
    total = len(valid) + len(flagged)
    print(f"\n{'─'*60}")
    print("VALIDATION REPORT")
    print(f"{'─'*60}")
    print(f"  Total rows        : {total:,}")
    print(f"  Valid rows        : {len(valid):,}  ({100*len(valid)/max(total,1):.1f}%)")
    print(f"  Flagged rows      : {len(flagged):,}  ({100*len(flagged)/max(total,1):.1f}%)")
    print(f"\n  NULL counts (valid rows):")
    t = null_counts.get("total_rows", total)
    for field in ("temperature", "salinity", "pressure_dbar"):
        n = null_counts.get(field, 0)
        print(f"    {field:<18}: {n:,} of {t:,}  ({100*n/max(t,1):.1f}%)")

    if flagged:
        # Show first 5 flagged rows as examples
        print(f"\n  Sample flagged rows (up to 5):")
        for row in flagged[:5]:
            fid   = row.get("float_id", "?")
            cycle = row.get("cycle_number", "?")
            pres  = row.get("pressure_dbar", "?")
            errs  = "; ".join(row.get("_validation_errors", []))
            print(f"    float={fid} cycle={cycle} pres={pres} dbar → {errs}")
    print(f"{'─'*60}\n")
