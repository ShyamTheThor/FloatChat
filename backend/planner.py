"""
backend/planner.py
==================
Deterministic natural language intent parser and rule-based fallback engine for FloatChat.
Provides high-precision semantic parsing for oceanographic queries, supporting DEMO MODE
and acting as a resilient fallback when LLM API services are unavailable or rate-limited.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from backend.schemas.query import QueryIntent, RegionBounds


# Standard Ocean Geographic Bounding Boxes
KNOWN_REGIONS = {
    "arabian sea": RegionBounds(min_lat=5.0, max_lat=25.0, min_lon=55.0, max_lon=80.0, region_name="Arabian Sea"),
    "bay of bengal": RegionBounds(min_lat=5.0, max_lat=22.0, min_lon=80.0, max_lon=100.0, region_name="Bay of Bengal"),
    "south indian ocean": RegionBounds(min_lat=-60.0, max_lat=-10.0, min_lon=20.0, max_lon=120.0, region_name="South Indian Ocean"),
    "southern ocean": RegionBounds(min_lat=-65.0, max_lat=-40.0, min_lon=20.0, max_lon=120.0, region_name="Southern Ocean"),
    "equatorial indian ocean": RegionBounds(min_lat=-5.0, max_lat=5.0, min_lon=50.0, max_lon=95.0, region_name="Equatorial Indian Ocean"),
    "indian ocean": RegionBounds(min_lat=-10.0, max_lat=25.0, min_lon=40.0, max_lon=105.0, region_name="Indian Ocean"),
}


MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12
}


def parse_intent_deterministic(query: str) -> QueryIntent:
    """
    Parse a user query deterministically using domain rules and regular expressions.
    Guarantees 100% valid Pydantic QueryIntent output without external API calls.
    """
    q = query.lower().strip()

    # 1. Parameter Extraction
    has_temp = bool(re.search(r"\b(temp|temperature|thermal|heat|celsius|°c)\b", q))
    has_sal = bool(re.search(r"\b(sal|salinity|salt|psu)\b", q))
    has_pres = bool(re.search(r"\b(pres|pressure|dbar|decibar)\b", q))
    has_depth = bool(re.search(r"\b(depth|depths)\b", q))

    if has_temp and has_sal:
        parameter = "all"
    elif has_sal:
        parameter = "salinity"
    elif has_temp:
        parameter = "temperature"
    elif has_pres:
        parameter = "pressure"
    elif has_depth:
        parameter = "depth"
    else:
        parameter = "all"

    # 2. Float ID extraction (extract first to prevent numeric ID colliding with depths)
    float_match = re.search(r"\bfloat\s+([a-zA-Z0-9]+)\b", q)
    float_id = float_match.group(1) if float_match else None
    q_no_float = re.sub(r"\bfloat\s+[a-zA-Z0-9]+\b", "", q)

    # 3. Date Range Extraction (extract before depth to avoid dates matching numeric depth ranges)
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    two_dates = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", q_no_float)
    if len(two_dates) >= 2:
        d1, d2 = two_dates[0], two_dates[1]
        if d1 <= d2:
            start_date, end_date = d1, d2
        else:
            start_date, end_date = d2, d1
    elif len(two_dates) == 1:
        start_date = two_dates[0]
        end_date = two_dates[0]
    else:
        # Month name: e.g. "in january 2023"
        month_match = re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})\b", q_no_float)
        if month_match:
            m_name = month_match.group(1)
            year = int(month_match.group(2))
            m_num = MONTH_MAP[m_name]
            start_date = f"{year:04d}-{m_num:02d}-01"
            end_day = 28 if m_num == 2 else 30 if m_num in (4, 6, 9, 11) else 31
            end_date = f"{year:04d}-{m_num:02d}-{end_day:02d}"

    # Strip dates from query string before checking depth numbers
    q_clean = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", q_no_float)

    # 4. Region Extraction
    detected_region: Optional[RegionBounds] = None
    if "bay of bengal" in q or "bengal" in q:
        detected_region = KNOWN_REGIONS["bay of bengal"]
    elif "arabian sea" in q or "arabian" in q:
        detected_region = KNOWN_REGIONS["arabian sea"]
    elif "south indian ocean" in q:
        detected_region = KNOWN_REGIONS["south indian ocean"]
    elif "equatorial" in q and "indian" in q:
        detected_region = KNOWN_REGIONS["equatorial indian ocean"]
    elif "southern ocean" in q:
        detected_region = KNOWN_REGIONS["southern ocean"]
    elif "indian ocean" in q:
        detected_region = KNOWN_REGIONS["indian ocean"]
    else:
        detected_region = KNOWN_REGIONS["indian ocean"]

    # 5. Depth Range Extraction
    min_depth: Optional[float] = None
    max_depth: Optional[float] = None
    target_depth: Optional[float] = None
    depth_tolerance: float = 15.0

    target_match = re.search(r"(?:at|depth|around|near)\s+(\d+(?:\.\d+)?)\s*(?:m|meter|meters|dbar)?\b", q_clean)
    if target_match and not re.search(r"(?:between|from)", q_clean):
        val = float(target_match.group(1))
        if val <= 11000:
            target_depth = val
            depth_tolerance = 25.0 if val >= 500 else 15.0
    elif "surface" in q_clean or "mixed layer" in q_clean or "upper layer" in q_clean or "upper ocean" in q_clean:
        min_depth = 0.0
        max_depth = 200.0
    elif "deep ocean" in q_clean or "deep water" in q_clean or "abyssal" in q_clean:
        min_depth = 200.0
        max_depth = 2000.0
    else:
        band_match = re.search(r"(?:between|from)?\s*(\d+(?:\.\d+)?)\s*(?:and|to|-)\s*(\d+(?:\.\d+)?)\s*(?:m|meter|meters|dbar)\b", q_clean)
        if band_match:
            d1 = float(band_match.group(1))
            d2 = float(band_match.group(2))
            if d1 <= 11000 and d2 <= 11000:
                if d1 <= d2:
                    min_depth, max_depth = d1, d2
                else:
                    min_depth, max_depth = d2, d1

    # 6. Visualization Extraction
    is_time_query = bool(re.search(r"\b(time|temporal|trend|trends|over time|through time|history|variation|timeseries|time series)\b", q))
    is_scatter_query = bool(re.search(r"\b(scatter|t-s|t/s|diagram|relationship|vs|versus|correlation)\b", q))
    is_map_query = bool(re.search(r"\b(where|map|location|locations|floats|positions|spatial|show floats|find floats)\b", q))
    is_profile_query = bool(re.search(r"\b(profile|vertical|water column|depth profile)\b", q))
    is_summary_query = bool(re.search(r"\b(average|mean|summary|overall|stats|statistics)\b", q))
    has_depth_constraint = (min_depth is not None or max_depth is not None or target_depth is not None)

    if is_time_query:
        visualization = "time_series"
    elif is_scatter_query:
        visualization = "scatter"
    elif is_profile_query or (has_depth_constraint and not is_map_query):
        visualization = "depth_profile"
    elif is_summary_query and not is_profile_query:
        visualization = "map"
    elif is_map_query and not (has_temp or has_sal) and not is_profile_query and not has_depth_constraint:
        visualization = "map"
    elif has_temp or has_sal or has_pres or has_depth:
        visualization = "depth_profile" if "map" not in q else "map"
    else:
        visualization = "map"

    # Float ID extraction if present: e.g. "float 2902275"
    float_match = re.search(r"\bfloat\s+([a-zA-Z0-9]+)\b", q)
    float_id = float_match.group(1) if float_match else None

    return QueryIntent(
        query_type="composite",
        parameter=parameter,
        visualization=visualization,
        region=detected_region,
        start_date=start_date,
        end_date=end_date,
        min_depth=min_depth,
        max_depth=max_depth,
        target_depth=target_depth,
        depth_tolerance=depth_tolerance,
        float_id=float_id,
    )
