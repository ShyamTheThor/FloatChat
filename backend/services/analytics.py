"""
backend/services/analytics.py
==============================
Server-side statistical analytics engine for ARGO observation results.
Calculates observation counts, float counts, min/max/mean metrics for
temperature, salinity, depth, and temporal range.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np
from backend.schemas.query import AnalyticsSummary


def compute_analytics(rows: List[Dict[str, Any]]) -> AnalyticsSummary:
    """
    Compute structured statistical metrics over a set of database profile rows.
    """
    if not rows:
        return AnalyticsSummary()

    obs_count = len(rows)

    # Unique floats and profiles
    floats = set()
    profiles = set()
    timestamps = []

    temps = []
    sals = []
    depths = []

    for r in rows:
        fid = r.get("float_id")
        cycle = r.get("cycle_number")
        if fid is not None:
            floats.add(str(fid))
            if cycle is not None:
                profiles.add(f"{fid}_{cycle}")

        ts = r.get("timestamp")
        if ts:
            timestamps.append(str(ts)[:10])

        t = r.get("temperature")
        if t is not None:
            temps.append(float(t))

        s = r.get("salinity")
        if s is not None:
            sals.append(float(s))

        d = r.get("depth_m")
        if d is not None:
            depths.append(float(d))

    timestamps.sort()
    earliest_date = timestamps[0] if timestamps else None
    latest_date = timestamps[-1] if timestamps else None

    temp_min = round(float(np.min(temps)), 2) if temps else None
    temp_max = round(float(np.max(temps)), 2) if temps else None
    temp_mean = round(float(np.mean(temps)), 2) if temps else None

    sal_min = round(float(np.min(sals)), 2) if sals else None
    sal_max = round(float(np.max(sals)), 2) if sals else None
    sal_mean = round(float(np.mean(sals)), 2) if sals else None

    depth_min = round(float(np.min(depths)), 1) if depths else None
    depth_max = round(float(np.max(depths)), 1) if depths else None

    return AnalyticsSummary(
        observation_count=obs_count,
        float_count=len(floats),
        profile_count=len(profiles) if profiles else len(floats),
        temp_min=temp_min,
        temp_max=temp_max,
        temp_mean=temp_mean,
        sal_min=sal_min,
        sal_max=sal_max,
        sal_mean=sal_mean,
        depth_min=depth_min,
        depth_max=depth_max,
        earliest_date=earliest_date,
        latest_date=latest_date,
    )
