"""
scripts/inspect_data.py
========================
Reads raw Argovis JSON files from data/raw/ and prints a human-readable
summary of every field, dimension, unit, and sample value — so the team
can verify the schema before building the pipeline.

Usage
-----
  python scripts/inspect_data.py [--data-dir data/raw] [--max-files 3]

Output includes:
  • Top-level keys in each profile
  • data_info: variable names, units, data modes
  • Shape of each data column (number of depth levels)
  • Min / max / mean for temperature, salinity, pressure
  • Latitude / longitude range
  • Timestamp range
  • Count of null values per variable
  • A sample of 3 depth levels from the first profile
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean, stdev


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_stats(values: list) -> dict:
    """Return min/max/mean/null_count for a list that may contain None."""
    nums = [v for v in values if v is not None and not math.isnan(v)]
    null_count = len(values) - len(nums)
    if not nums:
        return {"min": None, "max": None, "mean": None, "null_count": null_count, "n": 0}
    return {
        "min":        round(min(nums), 4),
        "max":        round(max(nums), 4),
        "mean":       round(mean(nums), 4),
        "null_count": null_count,
        "n":          len(nums),
    }


def _hline(char: str = "─", width: int = 72) -> str:
    return char * width


# ── Main inspection logic ─────────────────────────────────────────────────────

def inspect_file(path: Path, verbose: bool = False) -> dict:
    """Parse one Argovis JSON file and return aggregate statistics."""
    profiles: list[dict] = json.loads(path.read_text())
    if not profiles:
        print(f"  [!] {path.name} is empty — skipping")
        return {}

    print(f"\n{_hline('═')}")
    print(f"FILE: {path.name}   ({len(profiles)} profiles)")
    print(_hline('═'))

    # ── Top-level keys (from first profile) ──────────────────────────────
    first = profiles[0]
    print("\n[1] Top-level keys in each profile:")
    for k, v in first.items():
        if k == "data":
            print(f"    {k:<28}→ list of {len(v)} arrays, each length {len(v[0])}")
        elif isinstance(v, (dict, list)):
            print(f"    {k:<28}→ {type(v).__name__}")
        else:
            print(f"    {k:<28}→ {repr(v)}")

    # ── data_info (variable names + units) ───────────────────────────────
    data_info = first.get("data_info", [])
    var_names  = data_info[0] if len(data_info) > 0 else []
    unit_rows  = data_info[2] if len(data_info) > 2 else []

    print("\n[2] data_info — variables, units, data modes:")
    for i, var in enumerate(var_names):
        unit = unit_rows[i][0] if i < len(unit_rows) else "?"
        mode = unit_rows[i][1] if i < len(unit_rows) else "?"
        print(f"    [{i}] {var:<20} unit={unit:<20} mode={mode}")

    # ── Aggregate statistics across all profiles ──────────────────────────
    all_temp, all_sal, all_pres = [], [], []
    all_lats,  all_lons        = [], []
    all_timestamps             = []
    level_counts               = []

    temp_idx = var_names.index("temperature") if "temperature" in var_names else 0
    sal_idx  = var_names.index("salinity")    if "salinity"    in var_names else 1
    pres_idx = var_names.index("pressure")    if "pressure"    in var_names else 2

    for prof in profiles:
        coords = prof.get("geolocation", {}).get("coordinates", [None, None])
        all_lons.append(coords[0])
        all_lats.append(coords[1])
        all_timestamps.append(prof.get("timestamp", ""))

        data_arrays = prof.get("data", [])
        if len(data_arrays) > temp_idx:
            all_temp.extend(data_arrays[temp_idx])
        if len(data_arrays) > sal_idx:
            all_sal.extend(data_arrays[sal_idx])
        if len(data_arrays) > pres_idx:
            all_pres.extend(data_arrays[pres_idx])
            level_counts.append(len(data_arrays[pres_idx]))

    print("\n[3] Spatial coverage:")
    valid_lats = [x for x in all_lats if x is not None]
    valid_lons = [x for x in all_lons if x is not None]
    if valid_lats:
        print(f"    Latitude : {min(valid_lats):.3f}° → {max(valid_lats):.3f}°")
        print(f"    Longitude: {min(valid_lons):.3f}° → {max(valid_lons):.3f}°")

    print("\n[4] Temporal coverage:")
    valid_ts = [t for t in all_timestamps if t]
    if valid_ts:
        print(f"    Timestamp: {min(valid_ts)} → {max(valid_ts)}")

    print("\n[5] Depth level counts per profile:")
    if level_counts:
        print(f"    Min levels : {min(level_counts)}")
        print(f"    Max levels : {max(level_counts)}")
        print(f"    Mean levels: {mean(level_counts):.1f}")

    print("\n[6] Variable statistics (across all profiles & levels):")
    for label, vals in [("temperature (°C)", all_temp),
                         ("salinity    (psu)", all_sal),
                         ("pressure  (dbar)", all_pres)]:
        s = _safe_stats(vals)
        print(f"    {label}:")
        print(f"      n={s['n']}  nulls={s['null_count']}  "
              f"min={s['min']}  max={s['max']}  mean={s['mean']}")

    # ── Sample depth profile from first float ─────────────────────────────
    print(f"\n[7] Sample depth profile (first 5 levels of profile '{first['_id']}'):")
    d = first.get("data", [])
    temps = d[temp_idx] if len(d) > temp_idx else []
    sals  = d[sal_idx]  if len(d) > sal_idx  else []
    pres  = d[pres_idx] if len(d) > pres_idx else []
    print(f"    {'Level':<6} {'Pressure(dbar)':<18} {'Temp(°C)':<14} {'Salinity(psu)'}")
    print(f"    {'-'*6} {'-'*18} {'-'*14} {'-'*13}")
    for i in range(min(5, len(pres))):
        t = f"{temps[i]:.4f}" if temps[i] is not None else "NULL"
        s = f"{sals[i]:.4f}"  if sals[i]  is not None else "NULL"
        p = f"{pres[i]:.2f}"  if pres[i]  is not None else "NULL"
        print(f"    {i:<6} {p:<18} {t:<14} {s}")

    return {
        "file": path.name,
        "profile_count": len(profiles),
        "var_names": var_names,
        "temp_stats": _safe_stats(all_temp),
        "sal_stats":  _safe_stats(all_sal),
        "pres_stats": _safe_stats(all_pres),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Argovis JSON files")
    parser.add_argument("--data-dir",  type=str, default="data/raw",
                        help="Directory of JSON files (default: data/raw)")
    parser.add_argument("--max-files", type=int, default=5,
                        help="Max files to inspect (default: 5)")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    files    = sorted(data_dir.glob("argovis_*.json"))[: args.max_files]

    if not files:
        print(f"No argovis_*.json files found in {data_dir}/")
        print("Run: python scripts/fetch_sample_data.py  first.")
        return

    print(f"\nInspecting {len(files)} file(s) from {data_dir}/")

    summaries = []
    for f in files:
        result = inspect_file(f)
        if result:
            summaries.append(result)

    # ── Cross-file summary ────────────────────────────────────────────────
    if len(summaries) > 1:
        total_profiles = sum(s["profile_count"] for s in summaries)
        print(f"\n{_hline('═')}")
        print(f"CROSS-FILE SUMMARY")
        print(_hline('═'))
        print(f"  Files inspected : {len(summaries)}")
        print(f"  Total profiles  : {total_profiles}")
        print(f"\nConclusion: variable names to use in parser.py:")
        if summaries[0]["var_names"]:
            for i, v in enumerate(summaries[0]["var_names"]):
                print(f"  data[{i}] → {v}")
        print()


if __name__ == "__main__":
    main()
