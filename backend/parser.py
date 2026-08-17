"""
backend/parser.py
=================
Parses raw Argovis JSON profile objects into clean row dicts matching
the argo_profiles schema defined in docs/schema.md.

Design decisions
----------------
- One profile (one float surfacing) has N depth levels → produces N rows.
- NULL values in depth arrays are stored as NULL (not dropped).  This
  preserves data lineage; the validate module counts and reports them.
- Pressure → depth conversion uses the simplified Leroy formula which
  requires latitude.  Accuracy is ±0.5 % for 0–2000 m.
- `float_id` and `cycle_number` are parsed from the Argovis `_id` field
  (format: "{platform_id}_{cycle_number}").
- `data_mode` is taken from `data_info[2][pressure_index][1]` — all three
  variables share the same mode per profile in Argovis.
"""

from __future__ import annotations

import math
from typing import Any


# ── Depth conversion ──────────────────────────────────────────────────────────

def _pressure_to_depth(pressure_dbar: float, lat: float) -> float:
    """
    Convert pressure (dbar) → depth (m) using the simplified Lewy formula.

    Reference: Leroy & Parthiot (1998), simplified to 2nd order.
    Accurate to ±0.5% for ocean depths 0–7000 m.
    """
    sin2_lat = math.sin(math.radians(lat)) ** 2
    correction = 1.0 + 5.25e-3 * sin2_lat
    return round(pressure_dbar * 0.9927 * correction, 3)


# ── ID parsing ────────────────────────────────────────────────────────────────

def _parse_id(profile_id: str) -> tuple[str, int | None]:
    """
    Split Argovis _id 'PLATFORMID_CYCLE' into (float_id, cycle_number).

    Examples:
      '2902275_239' → ('2902275', 239)
      '1902345_001' → ('1902345', 1)
    """
    parts = profile_id.rsplit("_", maxsplit=1)
    float_id = parts[0]
    try:
        cycle_number = int(parts[1]) if len(parts) == 2 else None
    except ValueError:
        cycle_number = None
    return float_id, cycle_number


# ── Variable index resolution ─────────────────────────────────────────────────

def _resolve_indices(data_info: list) -> tuple[int, int, int]:
    """
    Return (temp_idx, sal_idx, pres_idx) from data_info[0].

    Falls back to (0, 1, 2) if data_info is missing — matches the Argovis
    default ordering for temperature, salinity, pressure.
    """
    if not data_info:
        return 0, 1, 2
    var_names = data_info[0] if data_info else []
    def _idx(name: str, default: int) -> int:
        try:
            return var_names.index(name)
        except ValueError:
            return default
    return (
        _idx("temperature", 0),
        _idx("salinity",    1),
        _idx("pressure",    2),
    )


# ── Core parser ───────────────────────────────────────────────────────────────

def parse_argovis_profile(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert one Argovis profile dict into a list of row dicts — one per depth level.

    Parameters
    ----------
    profile : dict
        A single element from the Argovis /argo JSON array response.

    Returns
    -------
    list[dict]
        Each dict matches the argo_profiles column names.
        Empty list is returned if the profile is missing required fields
        (lat/lon/timestamp).
    """
    profile_id = profile.get("_id", "")
    float_id, cycle_number = _parse_id(profile_id)

    # ── Required spatial / temporal fields ───────────────────────────────
    coords = profile.get("geolocation", {}).get("coordinates", [])
    if len(coords) < 2:
        return []          # no position → skip entirely
    lon, lat = coords[0], coords[1]

    timestamp = profile.get("timestamp")
    if not timestamp:
        return []          # no time → skip entirely

    # ── Optional metadata ─────────────────────────────────────────────────
    basin             = profile.get("basin")
    profile_direction = profile.get("profile_direction")

    source_list = profile.get("source", [])
    source_url  = source_list[0].get("url") if source_list else None

    # ── Variable arrays ───────────────────────────────────────────────────
    data_info = profile.get("data_info", [])
    data      = profile.get("data", [])

    temp_idx, sal_idx, pres_idx = _resolve_indices(data_info)

    temps = data[temp_idx] if temp_idx < len(data) else []
    sals  = data[sal_idx]  if sal_idx  < len(data) else []
    pres  = data[pres_idx] if pres_idx < len(data) else []

    # data_mode lives at data_info[2][any_var_idx][1]
    data_mode = None
    unit_rows = data_info[2] if len(data_info) > 2 else []
    if unit_rows and len(unit_rows[0]) > 1:
        data_mode = unit_rows[0][1]   # e.g. 'D', 'R', 'A'

    # ── Build one row per depth level ─────────────────────────────────────
    n_levels = max(len(temps), len(sals), len(pres))
    rows: list[dict[str, Any]] = []

    for i in range(n_levels):
        pressure_dbar = pres[i]  if i < len(pres)  else None
        temperature   = temps[i] if i < len(temps) else None
        salinity      = sals[i]  if i < len(sals)  else None

        # Compute depth only when pressure is not null
        depth_m = None
        if pressure_dbar is not None:
            depth_m = _pressure_to_depth(pressure_dbar, lat)

        rows.append({
            "float_id":          float_id,
            "cycle_number":      cycle_number,
            "lat":               lat,
            "lon":               lon,
            "timestamp":         timestamp,
            "pressure_dbar":     pressure_dbar,
            "depth_m":           depth_m,
            "temperature":       temperature,
            "salinity":          salinity,
            "basin":             basin,
            "profile_direction": profile_direction,
            "data_mode":         data_mode,
            "source_url":        source_url,
        })

    return rows


def parse_argovis_file(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Parse an entire list of Argovis profiles (one JSON file's worth).

    Returns a flat list of row dicts across all profiles and all levels.
    Profiles that fail required-field validation are silently skipped
    (they will be counted as 'skipped' in load_data.py).
    """
    all_rows: list[dict[str, Any]] = []
    for prof in profiles:
        all_rows.extend(parse_argovis_profile(prof))
    return all_rows
