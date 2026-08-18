"""
backend/rag.py
==============
Core logic for parsing natural language queries into structured database queries
using an LLM (Groq via OpenAI-compatible API) + ChromaDB metadata augmentation.

Uses Pydantic model validation to enforce strict query intent bounds.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI

from backend.schemas.query import QueryIntent, RegionBounds, AnalyticsSummary
from backend.queries import query_composite, get_dataset_metadata
from backend.services.analytics import compute_analytics
from backend.vector_store import init_vector_store, search_metadata
from backend.planner import parse_intent_deterministic

MODEL = "openai/gpt-oss-120b"

def is_demo_mode() -> bool:
    """Check if DEMO MODE is explicitly activated."""
    return os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")

SYSTEM_PROMPT = """You are FloatChat, an AI assistant for oceanographers querying ARGO ocean float data in the Indian Ocean.

Your job is to translate user natural language questions into a structured QueryIntent JSON object.

Output ONLY valid JSON matching this schema:
{
  "query_type": "composite",
  "parameter": "all",
  "visualization": "map",
  "region": {
    "min_lat": 5.0,
    "max_lat": 25.0,
    "min_lon": 55.0,
    "max_lon": 80.0,
    "region_name": "Arabian Sea"
  },
  "start_date": null,
  "end_date": null,
  "min_depth": null,
  "max_depth": null,
  "target_depth": null,
  "depth_tolerance": 15.0,
  "float_id": null
}

RULES:
1. Region bounding boxes (from context or standard ocean regions):
   - Arabian Sea: min_lat=5, max_lat=25, min_lon=55, max_lon=80
   - Bay of Bengal: min_lat=5, max_lat=22, min_lon=80, max_lon=100
   - Indian Ocean: min_lat=-10, max_lat=25, min_lon=40, max_lon=105
   - South Indian Ocean: min_lat=-60, max_lat=-10, min_lon=20, max_lon=120
2. Visualizations:
   - "salinity" or "temperature" depth queries -> "depth_profile"
   - "over time", "trend", "temporal" queries -> "time_series"
   - "where are the floats", "map", "locations" -> "map"
   - parameter vs parameter (e.g. salinity vs temp) -> "scatter"
3. Parameters:
   - Explicitly extract requested parameter: "temperature", "salinity", "pressure", "depth", or "all".
4. Depth shortcuts:
   - "surface" or "mixed layer" -> min_depth=0, max_depth=200
   - "deep ocean" -> min_depth=200, max_depth=2000
   - "at 100 meters" -> target_depth=100, depth_tolerance=15
5. Dates:
   - If user asks for specific dates/years, parse YYYY-MM-DD.
   - If user does NOT specify a date, leave start_date and end_date null (system will auto-bind to dataset coverage).
"""


def get_llm_client() -> OpenAI:
    """Initialize the OpenAI client pointing to Groq."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_api_key_here":
        raise ValueError("GROQ_API_KEY is not set in .env")
    return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")


def process_chat_query(user_message: str) -> dict[str, Any]:
    """
    Full RAG pipeline:
    1. Search ChromaDB for relevant domain context (region bounding boxes, parameters).
    2. Retrieve dataset coverage from PostgreSQL.
    3. Prompt LLM (Groq) or fallback to deterministic planner for structured QueryIntent.
    4. Validate intent with Pydantic.
    5. Execute parameterized SQL query against PostgreSQL.
    6. Compute server-side analytics.
    7. Generate LLM summary response (or deterministic summary).
    8. Return response payload.
    """
    if not user_message or not user_message.strip():
        user_message = "Show floats in Indian Ocean"

    # Ensure vector store is initialized
    init_vector_store()

    # Step 1: Query dataset metadata
    dataset_meta = get_dataset_metadata()

    # Step 2: Search ChromaDB for metadata context
    context_docs = search_metadata(user_message, n_results=3)
    context_text = "\n".join([c["text"] for c in context_docs])

    # Step 3: Intent Parsing (Live LLM with deterministic planner fallback / DEMO MODE)
    intent: Optional[QueryIntent] = None

    if is_demo_mode():
        print(f"[RAG] Running in DEMO MODE: using deterministic semantic planner.")
        intent = parse_intent_deterministic(user_message)
    else:
        try:
            client = get_llm_client()
            query_messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Dataset Coverage: Earliest={dataset_meta.get('earliest_date')}, Latest={dataset_meta.get('latest_date')}, Total Floats={dataset_meta.get('total_floats')}\n\n"
                        f"Context from knowledge base:\n{context_text}\n\n"
                        f"User question: {user_message}"
                    ),
                },
            ]

            routing_response = client.chat.completions.create(
                model=MODEL,
                messages=query_messages,
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            raw_json = routing_response.choices[0].message.content.strip()
            print(f"[RAG] Raw LLM intent response: {raw_json}")
            raw_dict = json.loads(raw_json)
            intent = QueryIntent.model_validate(raw_dict)
        except Exception as e:
            print(f"[RAG] LLM parsing unavailable or validation fallback ({e}). Using deterministic planner.")
            intent = parse_intent_deterministic(user_message)

    # Auto-bind default dates to dataset coverage if unspecified
    start_date = intent.start_date
    end_date = intent.end_date
    if not start_date and not end_date and dataset_meta.get("earliest_date"):
        start_date = dataset_meta.get("earliest_date")
        end_date = dataset_meta.get("latest_date")

    # Step 4: Execute database query
    min_lat = intent.region.min_lat if intent.region else None
    max_lat = intent.region.max_lat if intent.region else None
    min_lon = intent.region.min_lon if intent.region else None
    max_lon = intent.region.max_lon if intent.region else None

    try:
        data = query_composite(
            min_lat=min_lat,
            max_lat=max_lat,
            min_lon=min_lon,
            max_lon=max_lon,
            start_date=start_date,
            end_date=end_date,
            min_depth=intent.min_depth,
            max_depth=intent.max_depth,
            target_depth=intent.target_depth,
            depth_tolerance=intent.depth_tolerance or 15.0,
            parameter=intent.parameter,
            float_id=intent.float_id,
        )
    except Exception as e:
        print(f"[RAG] Database query execution failed: {e}")
        return {
            "answer": "Ocean data is temporarily unavailable. Please verify database connection.",
            "data": [],
            "plot_type": "none",
            "intent": intent.model_dump(),
            "analytics": AnalyticsSummary().model_dump(),
        }

    # Step 5: Analytics calculation
    analytics = compute_analytics(data)

    if analytics.observation_count == 0:
        cov_info = f"covers {dataset_meta.get('earliest_date')} to {dataset_meta.get('latest_date')}" if dataset_meta.get("earliest_date") else "is currently empty"
        return {
            "answer": f"No ARGO float observations matched those specific criteria. The loaded dataset {cov_info}. Try searching for the Arabian Sea or Bay of Bengal.",
            "data": [],
            "plot_type": "none",
            "intent": intent.model_dump(),
            "analytics": analytics.model_dump(),
        }

    # Step 6: LLM natural language summary response
    summary_messages = [
        {
            "role": "system",
            "content": (
                "You are FloatChat, an expert ocean science assistant. "
                "Provide a clear, professional 2-3 sentence summary of the ARGO observation results. "
                "Highlight observation counts, float count, depth range, and key metric averages (temperature/salinity)."
            ),
        },
        {
            "role": "user",
            "content": (
                f"User Question: \"{user_message}\"\n"
                f"Query Intent: {intent.model_dump()}\n"
                f"Analytics Summary: {analytics.model_dump()}\n"
                f"Sample Observation: {data[0] if data else {}}"
            ),
        },
    ]

    answer = None
    if not is_demo_mode():
        try:
            client = get_llm_client()
            summary_messages = [
                {
                    "role": "system",
                    "content": (
                        "You are FloatChat, an expert ocean science assistant. "
                        "Provide a clear, professional 2-3 sentence summary of the ARGO observation results. "
                        "Highlight observation counts, float count, depth range, and key metric averages (temperature/salinity)."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"User Question: \"{user_message}\"\n"
                        f"Query Intent: {intent.model_dump()}\n"
                        f"Analytics Summary: {analytics.model_dump()}\n"
                        f"Sample Observation: {data[0] if data else {}}"
                    ),
                },
            ]
            summary_response = client.chat.completions.create(
                model=MODEL,
                messages=summary_messages,
                temperature=0.4,
            )
            answer = summary_response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[RAG] Summary generation LLM fallback due to: {e}")

    if not answer:
        reg_name = intent.region.region_name if intent.region else "the selected ocean region"
        depth_info = f" spanning depths from {analytics.depth_min} m to {analytics.depth_max} m" if analytics.depth_min is not None else ""
        temp_info = f" Mean temperature is {analytics.temp_mean} °C (range: {analytics.temp_min}–{analytics.temp_max} °C)." if analytics.temp_mean is not None else ""
        sal_info = f" Mean practical salinity is {analytics.sal_mean} psu (range: {analytics.sal_min}–{analytics.sal_max} psu)." if analytics.sal_mean is not None else ""
        answer = (
            f"Retrieved {analytics.observation_count:,} ARGO observations across {analytics.float_count} unique floats in {reg_name}{depth_info}."
            f"{temp_info}{sal_info}"
        )

    return {
        "answer": answer,
        "data": data[:1000],  # cap at 1000 observations for smooth UI rendering
        "plot_type": intent.visualization,
        "intent": intent.model_dump(),
        "analytics": analytics.model_dump(),
    }


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print("Testing process_chat_query('Show me salinity in the Arabian Sea')...")
    res = process_chat_query("Show me salinity in the Arabian Sea")
    print("Answer:", res["answer"])
    print("Plot type:", res["plot_type"])
    print("Analytics:", res["analytics"])

