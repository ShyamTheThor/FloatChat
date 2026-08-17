"""
scripts/fetch_sample_data.py
============================
Downloads sample ARGO float profiles from Argovis (argovis.colorado.edu)
for the Indian Ocean region (Arabian Sea + Bay of Bengal).

ARGOVIS API NOTES
-----------------
- Base URL:  https://argovis-api.colorado.edu/argo
- Docs:      https://argovis-api.colorado.edu/docs
- Auth:      Anonymous access is fine for small queries.
             Register at https://argovis.colorado.edu/ for a token if you
             hit rate limits.  Set env var ARGOVIS_TOKEN if you have one.
- Polygon:   GeoJSON coordinate ring  [[lon,lat], ...] — MUST close (first
             == last point).  Lon comes before lat per GeoJSON spec.
- data param: comma-separated variables, e.g. "temperature,salinity,pressure"

INCOIS / GDAC ALTERNATIVE (for teams that need official NetCDF)
---------------------------------------------------------------
Indian ARGO floats (managed by INCOIS) are mirrored at:
  ftp://ftp.ifremer.fr/ifremer/argo/dac/incois/
Each float has its own sub-directory, e.g.:
  ftp://ftp.ifremer.fr/ifremer/argo/dac/incois/2902275/profiles/
Individual profile files follow the naming convention:
  {mode}{float_id}_{cycle:03d}.nc
  e.g.  D2902275_239.nc  (D = delayed-mode, R = real-time, S = synthetic-BGC)

Download them with:
  wget -r -np -nH --cut-dirs=6 --accept "*.nc" \
    ftp://ftp.ifremer.fr/ifremer/argo/dac/incois/2902275/profiles/

Then parse with xarray:
  import xarray as xr
  ds = xr.open_dataset("D2902275_239.nc", engine="netcdf4")
  print(ds.data_vars)   # TEMP, PSAL, PRES, JULD, LATITUDE, LONGITUDE, ...

Usage
-----
  python scripts/fetch_sample_data.py [--days 7] [--out-dir data/raw]

The script will create one JSON file per day:
  data/raw/argovis_indian_ocean_YYYY-MM-DD.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL = "https://argovis-api.colorado.edu/argo"

# Indian Ocean bounding polygon (GeoJSON ring — lon first, lat second)
# Covers Arabian Sea + Bay of Bengal, with Indian sub-continent excluded
# by keeping a wide rectangle: lon 40–105, lat -10–25
INDIAN_OCEAN_POLYGON = [
    [40.0, -10.0],
    [105.0, -10.0],
    [105.0, 25.0],
    [40.0, 25.0],
    [40.0, -10.0],   # close the ring
]

VARIABLES = "temperature,salinity,pressure"

DEFAULT_START = date(2023, 1, 1)
DEFAULT_DAYS = 7    # fetch one week → usually 50-300 profiles


# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_profiles(start: date, end: date, token: str | None = None) -> list[dict]:
    """Fetch all ARGO profiles in the Indian Ocean window [start, end)."""
    params = {
        "startDate": start.isoformat() + "T00:00:00Z",
        "endDate":   end.isoformat()   + "T00:00:00Z",
        "polygon":   json.dumps(INDIAN_OCEAN_POLYGON),
        "data":      VARIABLES,
    }
    headers = {}
    if token:
        headers["x-argokey"] = token

    print(f"  → GET {BASE_URL}  {start} → {end}", end="", flush=True)
    resp = requests.get(BASE_URL, params=params, headers=headers, timeout=120)
    resp.raise_for_status()

    profiles: list[dict] = resp.json()
    print(f"  [{len(profiles)} profiles]")
    return profiles


def save_profiles(profiles: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(profiles, fh, indent=2)
    print(f"  ✓ Saved {len(profiles)} profiles → {path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch ARGO sample data from Argovis")
    parser.add_argument("--days",    type=int,  default=DEFAULT_DAYS,
                        help="Number of days to fetch (default: 7)")
    parser.add_argument("--out-dir", type=str,  default="data/raw",
                        help="Output directory (default: data/raw)")
    parser.add_argument("--start",   type=str,  default=DEFAULT_START.isoformat(),
                        help="Start date YYYY-MM-DD (default: 2023-01-01)")
    args = parser.parse_args()

    token     = os.environ.get("ARGOVIS_TOKEN")
    out_dir   = Path(args.out_dir)
    start     = date.fromisoformat(args.start)
    total     = 0
    all_files: list[Path] = []

    # Fetch one file per day to stay within Argovis size limits
    print(f"\nFetching {args.days} days of Indian Ocean ARGO profiles from Argovis …\n")
    for i in range(args.days):
        day      = start + timedelta(days=i)
        next_day = day   + timedelta(days=1)
        out_path = out_dir / f"argovis_indian_ocean_{day.isoformat()}.json"

        if out_path.exists():
            existing = json.loads(out_path.read_text())
            print(f"  ↩  {out_path.name} already exists ({len(existing)} profiles) — skipping")
            total += len(existing)
            all_files.append(out_path)
            continue

        try:
            profiles = fetch_profiles(day, next_day, token=token)
        except requests.HTTPError as exc:
            print(f"\n  ✗ HTTP {exc.response.status_code} for {day} — skipping")
            continue
        except Exception as exc:
            print(f"\n  ✗ Error for {day}: {exc} — skipping")
            continue

        if profiles:
            save_profiles(profiles, out_path)
            all_files.append(out_path)
            total += len(profiles)

        # Be polite to the API
        time.sleep(0.5)

    print(f"\n{'─'*60}")
    print(f"Done. {total} total profiles across {len(all_files)} file(s).")
    print(f"Files in {out_dir}/:")
    for f in all_files:
        size_kb = f.stat().st_size / 1024
        print(f"  {f.name}  ({size_kb:.1f} KB)")
    print(f"\nNext step:\n  python scripts/inspect_data.py --data-dir {out_dir}\n")


if __name__ == "__main__":
    main()
