"""
scripts/eval_planner.py
=======================
Evaluation benchmark for FloatChat's natural language ocean query planner.
Tests a 40-query dataset across all standard oceanographic dimensions:
- Parameter extraction (temperature, salinity, pressure, depth, all)
- Geographic bounding boxes (Arabian Sea, Bay of Bengal, Indian Ocean, etc.)
- Temporal constraints (exact dates, ranges, months)
- Vertical depth constraints (surface layer, deep ocean, target depths)
- Scientific visualization mapping (depth_profile, time_series, scatter, map)
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.schemas.query import QueryIntent
from backend.planner import parse_intent_deterministic

# 40 Representative Oceanographic Test Queries
BENCHMARK_SET: List[Dict[str, Any]] = [
    # ── 1. Regional Salinity Queries ──
    {
        "query": "Show me salinity in the Arabian Sea",
        "expected": {
            "parameter": "salinity",
            "region_name": "Arabian Sea",
            "min_lat": 5.0, "max_lat": 25.0, "min_lon": 55.0, "max_lon": 80.0,
            "visualization": "depth_profile"
        }
    },
    {
        "query": "What is the salinity profile in the Bay of Bengal?",
        "expected": {
            "parameter": "salinity",
            "region_name": "Bay of Bengal",
            "min_lat": 5.0, "max_lat": 22.0, "min_lon": 80.0, "max_lon": 100.0,
            "visualization": "depth_profile"
        }
    },
    {
        "query": "Display salinity distribution across the Indian Ocean",
        "expected": {
            "parameter": "salinity",
            "region_name": "Indian Ocean",
            "visualization": "depth_profile"
        }
    },
    {
        "query": "Salinity observations in South Indian Ocean",
        "expected": {
            "parameter": "salinity",
            "region_name": "South Indian Ocean",
            "min_lat": -60.0, "max_lat": -10.0, "min_lon": 20.0, "max_lon": 120.0,
            "visualization": "depth_profile"
        }
    },

    # ── 2. Regional Temperature Queries ──
    {
        "query": "Show temperature in the Bay of Bengal",
        "expected": {
            "parameter": "temperature",
            "region_name": "Bay of Bengal",
            "visualization": "depth_profile"
        }
    },
    {
        "query": "What is the thermal structure in the Arabian Sea?",
        "expected": {
            "parameter": "temperature",
            "region_name": "Arabian Sea",
            "visualization": "depth_profile"
        }
    },
    {
        "query": "Temperature in Equatorial Indian Ocean",
        "expected": {
            "parameter": "temperature",
            "region_name": "Equatorial Indian Ocean",
            "min_lat": -5.0, "max_lat": 5.0,
            "visualization": "depth_profile"
        }
    },

    # ── 3. Time Series & Trend Queries ──
    {
        "query": "Show temperature over time",
        "expected": {
            "parameter": "temperature",
            "visualization": "time_series"
        }
    },
    {
        "query": "Salinity trend through time in the Arabian Sea",
        "expected": {
            "parameter": "salinity",
            "region_name": "Arabian Sea",
            "visualization": "time_series"
        }
    },
    {
        "query": "Temporal variation of surface temperature in Bay of Bengal",
        "expected": {
            "parameter": "temperature",
            "region_name": "Bay of Bengal",
            "min_depth": 0.0, "max_depth": 200.0,
            "visualization": "time_series"
        }
    },
    {
        "query": "How has ocean temperature changed over time?",
        "expected": {
            "parameter": "temperature",
            "visualization": "time_series"
        }
    },
    {
        "query": "Show historical salinity variation",
        "expected": {
            "parameter": "salinity",
            "visualization": "time_series"
        }
    },

    # ── 4. Spatial Map & Location Queries ──
    {
        "query": "Show floats in the Arabian Sea",
        "expected": {
            "region_name": "Arabian Sea",
            "visualization": "map"
        }
    },
    {
        "query": "Where are the active ARGO floats in Bay of Bengal?",
        "expected": {
            "region_name": "Bay of Bengal",
            "visualization": "map"
        }
    },
    {
        "query": "Display float positions in the Indian Ocean",
        "expected": {
            "region_name": "Indian Ocean",
            "visualization": "map"
        }
    },
    {
        "query": "Map float locations",
        "expected": {
            "visualization": "map"
        }
    },

    # ── 5. Specific Depth & Depth Band Queries ──
    {
        "query": "Show temperature at 100 meters in Arabian Sea",
        "expected": {
            "parameter": "temperature",
            "region_name": "Arabian Sea",
            "target_depth": 100.0,
            "visualization": "depth_profile"
        }
    },
    {
        "query": "Salinity at 500m depth",
        "expected": {
            "parameter": "salinity",
            "target_depth": 500.0,
            "visualization": "depth_profile"
        }
    },
    {
        "query": "Surface layer temperature between 0 and 200m",
        "expected": {
            "parameter": "temperature",
            "min_depth": 0.0, "max_depth": 200.0,
            "visualization": "depth_profile"
        }
    },
    {
        "query": "Deep ocean observations between 200 and 2000m in Arabian Sea",
        "expected": {
            "region_name": "Arabian Sea",
            "min_depth": 200.0, "max_depth": 2000.0,
            "visualization": "depth_profile"
        }
    },
    {
        "query": "Show temperature at 500m over time",
        "expected": {
            "parameter": "temperature",
            "target_depth": 500.0,
            "visualization": "time_series"
        }
    },

    # ── 6. Multi-parameter & T-S Scatter Diagrams ──
    {
        "query": "Show temperature and salinity in the Arabian Sea",
        "expected": {
            "parameter": "all",
            "region_name": "Arabian Sea",
            "visualization": "depth_profile"
        }
    },
    {
        "query": "Generate a T-S scatter diagram for the Bay of Bengal",
        "expected": {
            "region_name": "Bay of Bengal",
            "visualization": "scatter"
        }
    },
    {
        "query": "Temperature versus salinity relationship",
        "expected": {
            "visualization": "scatter"
        }
    },
    {
        "query": "Show T-S diagram in the Indian Ocean",
        "expected": {
            "region_name": "Indian Ocean",
            "visualization": "scatter"
        }
    },

    # ── 7. Date Filtered Queries ──
    {
        "query": "Show Arabian Sea data between 2023-01-01 and 2023-01-10",
        "expected": {
            "region_name": "Arabian Sea",
            "start_date": "2023-01-01",
            "end_date": "2023-01-10",
            "visualization": "map"
        }
    },
    {
        "query": "Floats observed in January 2023",
        "expected": {
            "start_date": "2023-01-01",
            "end_date": "2023-01-31",
            "visualization": "map"
        }
    },
    {
        "query": "Temperature profile on 2023-01-05 in Bay of Bengal",
        "expected": {
            "parameter": "temperature",
            "region_name": "Bay of Bengal",
            "start_date": "2023-01-05",
            "visualization": "depth_profile"
        }
    },

    # ── 8. Single Float Specific Queries ──
    {
        "query": "Show profile for float 2902275",
        "expected": {
            "float_id": "2902275",
            "visualization": "depth_profile"
        }
    },
    {
        "query": "Where is float 1902345 located?",
        "expected": {
            "float_id": "1902345",
            "visualization": "map"
        }
    },

    # ── 9. Ambiguous & Generic Questions ──
    {
        "query": "Give me the average temperature",
        "expected": {
            "parameter": "temperature",
            "visualization": "map"
        }
    },
    {
        "query": "Show ocean data",
        "expected": {
            "parameter": "all",
            "visualization": "map"
        }
    },
    {
        "query": "What is the water condition?",
        "expected": {
            "parameter": "all",
            "visualization": "map"
        }
    },
    {
        "query": "Show observations",
        "expected": {
            "parameter": "all",
            "visualization": "map"
        }
    },

    # ── 10. Pressure / Vertical Coordinates ──
    {
        "query": "Show pressure measurements in Arabian Sea",
        "expected": {
            "parameter": "pressure",
            "region_name": "Arabian Sea",
            "visualization": "depth_profile"
        }
    },
    {
        "query": "Vertical pressure profiles in Bay of Bengal",
        "expected": {
            "parameter": "pressure",
            "region_name": "Bay of Bengal",
            "visualization": "depth_profile"
        }
    },

    # ── 11. Boundary / Zero-Result Geographic Queries ──
    {
        "query": "Show data for Southern Ocean below 40S",
        "expected": {
            "region_name": "Southern Ocean",
            "visualization": "map"
        }
    },
    {
        "query": "Floats in Arctic Ocean",
        "expected": {
            "visualization": "map"
        }
    },
    {
        "query": "Show salinity in North Atlantic",
        "expected": {
            "parameter": "salinity",
            "visualization": "depth_profile"
        }
    },
    {
        "query": "Surface water salinity",
        "expected": {
            "parameter": "salinity",
            "min_depth": 0.0, "max_depth": 200.0,
            "visualization": "depth_profile"
        }
    }
]


def run_benchmark() -> Dict[str, Any]:
    """Execute the full 40-query benchmark and compute multidimensional accuracy."""
    total = len(BENCHMARK_SET)
    passed = 0
    param_matches = 0
    region_matches = 0
    vis_matches = 0
    depth_matches = 0
    date_matches = 0

    failures = []

    print(f"\n{'='*70}")
    print(f"FLOATCAT AI QUERY PLANNER BENCHMARK ({total} Test Queries)")
    print(f"{'='*70}\n")

    for i, test_case in enumerate(BENCHMARK_SET, 1):
        q = test_case["query"]
        exp = test_case["expected"]

        # Run deterministic planner
        intent: QueryIntent = parse_intent_deterministic(q)

        # Dimension checks
        param_ok = (exp.get("parameter") is None) or (intent.parameter == exp["parameter"])
        
        region_ok = True
        if exp.get("region_name"):
            region_ok = (intent.region is not None) and (intent.region.region_name == exp["region_name"])
            if exp.get("min_lat") is not None and intent.region:
                region_ok = region_ok and (intent.region.min_lat == exp["min_lat"])

        vis_ok = (exp.get("visualization") is None) or (intent.visualization == exp["visualization"])

        depth_ok = True
        if exp.get("target_depth") is not None:
            depth_ok = depth_ok and (intent.target_depth == exp["target_depth"])
        if exp.get("min_depth") is not None:
            depth_ok = depth_ok and (intent.min_depth == exp["min_depth"])
        if exp.get("max_depth") is not None:
            depth_ok = depth_ok and (intent.max_depth == exp["max_depth"])

        date_ok = True
        if exp.get("start_date"):
            date_ok = date_ok and (intent.start_date == exp["start_date"])
        if exp.get("end_date"):
            date_ok = date_ok and (intent.end_date == exp["end_date"])

        float_ok = True
        if exp.get("float_id"):
            float_ok = (intent.float_id == exp["float_id"])

        all_ok = param_ok and region_ok and vis_ok and depth_ok and date_ok and float_ok

        if param_ok: param_matches += 1
        if region_ok: region_matches += 1
        if vis_ok: vis_matches += 1
        if depth_ok: depth_matches += 1
        if date_ok: date_matches += 1

        status = "✓ PASS" if all_ok else "✗ FAIL"
        if all_ok:
            passed += 1
            print(f"[{i:02d}/40] {status} | \"{q[:42]}\" -> param={intent.parameter}, vis={intent.visualization}, reg={intent.region.region_name if intent.region else 'None'}")
        else:
            print(f"[{i:02d}/40] {status} | \"{q}\"")
            print(f"       Expected: {exp}")
            print(f"       Got:      param={intent.parameter}, vis={intent.visualization}, reg={intent.region.region_name if intent.region else 'None'}, depth=({intent.min_depth},{intent.max_depth},t={intent.target_depth}), date=({intent.start_date},{intent.end_date})")
            failures.append({"query": q, "expected": exp, "got": intent.model_dump()})

    overall_accuracy = (passed / total) * 100
    param_acc = (param_matches / total) * 100
    region_acc = (region_matches / total) * 100
    vis_acc = (vis_matches / total) * 100
    depth_acc = (depth_matches / total) * 100
    date_acc = (date_matches / total) * 100

    print(f"\n{'-'*70}")
    print("BENCHMARK EVALUATION SUMMARY")
    print(f"{'-'*70}")
    print(f"  Total Queries Evaluated : {total}")
    print(f"  Total Passed (100% Match): {passed} / {total} ({overall_accuracy:.1f}%)")
    print(f"  Parameter Accuracy      : {param_matches} / {total} ({param_acc:.1f}%)")
    print(f"  Region Accuracy         : {region_matches} / {total} ({region_acc:.1f}%)")
    print(f"  Visualization Accuracy  : {vis_matches} / {total} ({vis_acc:.1f}%)")
    print(f"  Depth Range Accuracy    : {depth_matches} / {total} ({depth_acc:.1f}%)")
    print(f"  Date Range Accuracy     : {date_matches} / {total} ({date_acc:.1f}%)")
    print(f"{'='*70}\n")

    return {
        "total": total,
        "passed": passed,
        "overall_accuracy": overall_accuracy,
        "param_acc": param_acc,
        "region_acc": region_acc,
        "vis_acc": vis_acc,
        "depth_acc": depth_acc,
        "date_acc": date_acc,
        "failures": failures
    }


if __name__ == "__main__":
    results = run_benchmark()
    if results["overall_accuracy"] < 95.0:
        sys.exit(1)
