"""
backend/schemas/query.py
========================
Pydantic schemas for LLM query intent validation and API request/response objects.
"""

from __future__ import annotations

from typing import Literal, Optional, Any, List, Dict
from pydantic import BaseModel, Field, field_validator


class RegionBounds(BaseModel):
    min_lat: float = Field(default=-90.0, ge=-90.0, le=90.0)
    max_lat: float = Field(default=90.0, ge=-90.0, le=90.0)
    min_lon: float = Field(default=-180.0, ge=-180.0, le=180.0)
    max_lon: float = Field(default=180.0, ge=-180.0, le=180.0)
    region_name: Optional[str] = "Custom Box"

    @field_validator("max_lat")
    @classmethod
    def validate_lat(cls, v: float, info) -> float:
        min_lat = info.data.get("min_lat")
        if min_lat is not None and v < min_lat:
            raise ValueError("max_lat must be greater than or equal to min_lat")
        return v

    @field_validator("max_lon")
    @classmethod
    def validate_lon(cls, v: float, info) -> float:
        min_lon = info.data.get("min_lon")
        if min_lon is not None and v < min_lon:
            raise ValueError("max_lon must be greater than or equal to min_lon")
        return v


class QueryIntent(BaseModel):
    query_type: Literal["region", "date_range", "depth_band", "composite", "dataset_metadata"] = "composite"
    parameter: Literal["temperature", "salinity", "pressure", "depth", "all"] = "all"
    visualization: Literal["map", "depth_profile", "time_series", "scatter", "table"] = "map"
    region: Optional[RegionBounds] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    min_depth: Optional[float] = Field(default=None, ge=0.0, le=11000.0)
    max_depth: Optional[float] = Field(default=None, ge=0.0, le=11000.0)
    target_depth: Optional[float] = Field(default=None, ge=0.0, le=11000.0)
    depth_tolerance: Optional[float] = Field(default=15.0, ge=1.0, le=500.0)
    float_id: Optional[str] = None

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v_str = str(v).strip()
        # Accept YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
        import re
        from datetime import datetime
        date_pattern = r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?$"
        if not re.match(date_pattern, v_str):
            raise ValueError(f"Invalid date format: '{v_str}'. Expected YYYY-MM-DD.")
        try:
            # Verify valid calendar date
            base_date = v_str[:10]
            datetime.strptime(base_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid calendar date: '{v_str}'")
        return base_date

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v: Optional[str], info) -> Optional[str]:
        start_date = info.data.get("start_date")
        if v is not None and start_date is not None and v < start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        return v

    @field_validator("max_depth")
    @classmethod
    def validate_depth(cls, v: Optional[float], info) -> Optional[float]:
        min_depth = info.data.get("min_depth")
        if v is not None and min_depth is not None and v < min_depth:
            raise ValueError("max_depth must be greater than or equal to min_depth")
        return v


class AnalyticsSummary(BaseModel):
    observation_count: int = 0
    float_count: int = 0
    profile_count: int = 0
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    temp_mean: Optional[float] = None
    sal_min: Optional[float] = None
    sal_max: Optional[float] = None
    sal_mean: Optional[float] = None
    depth_min: Optional[float] = None
    depth_max: Optional[float] = None
    earliest_date: Optional[str] = None
    latest_date: Optional[str] = None


class ChatResponseSchema(BaseModel):
    answer: str
    data: List[Dict[str, Any]]
    plot_type: str
    intent: Dict[str, Any]
    analytics: AnalyticsSummary
