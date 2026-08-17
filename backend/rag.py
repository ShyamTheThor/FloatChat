"""
backend/rag.py
==============
Core logic for parsing natural language queries into structured database queries
using an LLM (Groq via OpenAI-compatible API) + ChromaDB metadata augmentation.

Uses JSON-mode structured output (compatible with all Groq models) instead of
function calling, which is not universally supported.
"""

import os
import json
from datetime import datetime, timezone
from openai import OpenAI
from backend.vector_store import search_metadata, init_vector_store
from backend.queries import query_by_region, query_by_date_range, query_by_depth_band

MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """You are FloatChat, an AI assistant for oceanographers querying ARGO ocean float data in the Indian Ocean.

Your job is to translate natural language questions into ONE structured database query.

You MUST respond with ONLY valid JSON (no markdown, no explanation) matching exactly one of these schemas:

1. Geographic region query:
   {"query_type": "region", "args": {"min_lat": <float>, "max_lat": <float>, "min_lon": <float>, "max_lon": <float>}}

2. Date range query:
   {"query_type": "date_range", "args": {"start_date": "<YYYY-MM-DD>", "end_date": "<YYYY-MM-DD>"}}

3. Depth band query:
   {"query_type": "depth_band", "args": {"min_depth": <float>, "max_depth": <float>}}

IMPORTANT RULES:
- Output ONLY the JSON object. No other text.
- If a named region is mentioned, use the bounding box from the context provided.
- If a date range cannot be determined, default to the last 7 days from today.
- For "surface" or "mixed layer", use depth 0–200 m.
- For "deep ocean", use depth 200–4000 m.
- If unsure of the query type, prefer "region" using the full Indian Ocean: min_lat=-10, max_lat=25, min_lon=40, max_lon=105.
"""


def get_llm_client() -> OpenAI:
    """Initialize the OpenAI client pointing to Groq."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_api_key_here":
        raise ValueError("GROQ_API_KEY is not set in .env")
    return OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")


def _run_query(query_type: str, args: dict) -> tuple[list[dict], str]:
    """Execute the appropriate DB query and return (data, plot_type)."""
    if query_type == "region":
        data = query_by_region(args["min_lat"], args["max_lat"], args["min_lon"], args["max_lon"])
        return data, "map"
    elif query_type == "date_range":
        data = query_by_date_range(args["start_date"], args["end_date"])
        return data, "time_series"
    elif query_type == "depth_band":
        data = query_by_depth_band(args["min_depth"], args["max_depth"])
        return data, "depth_profile"
    else:
        return [], "none"


def process_chat_query(user_message: str) -> dict:
    """
    Full RAG pipeline:
    1. Search ChromaDB for relevant context (region bounding boxes, param info).
    2. Prompt LLM (Groq) to return a structured JSON query.
    3. Execute the query against PostgreSQL.
    4. Ask LLM to summarize the result in natural language.
    5. Return: { answer, data, plot_type }
    """
    # Ensure vector store is ready
    init_vector_store()

    client = get_llm_client()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # --- Step 1: RAG retrieval ---
    context_docs = search_metadata(user_message, n_results=3)
    context_text = "\n".join([c["text"] for c in context_docs])

    # --- Step 2: LLM → structured JSON query ---
    query_messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": (
                f"Today is {today}.\n\n"
                f"Context from knowledge base:\n{context_text}\n\n"
                f"User question: {user_message}"
            )
        }
    ]

    routing_response = client.chat.completions.create(
        model=MODEL,
        messages=query_messages,
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    raw_json = routing_response.choices[0].message.content.strip()
    print(f"[RAG] LLM routing response: {raw_json}")

    try:
        parsed = json.loads(raw_json)
        query_type = parsed["query_type"]
        args = parsed["args"]
    except (json.JSONDecodeError, KeyError) as e:
        return {
            "answer": "I couldn't understand what data you're looking for. Please try rephrasing your question (e.g. 'Show me temperature in the Arabian Sea').",
            "data": [],
            "plot_type": "none"
        }

    # --- Step 3: Execute DB query ---
    try:
        data, plot_type = _run_query(query_type, args)
    except Exception as e:
        return {
            "answer": f"I understood your query but encountered a database error: {str(e)}",
            "data": [],
            "plot_type": "none"
        }

    count = len(data)
    print(f"[RAG] query_type={query_type}, args={args} → {count} rows, plot_type={plot_type}")

    if count == 0:
        return {
            "answer": "No data was found for that query. The Indian Ocean ARGO dataset covers Jan 2023. Try asking about the Arabian Sea, Bay of Bengal, or a date range within Jan 1–7, 2023.",
            "data": [],
            "plot_type": "none"
        }

    # --- Step 4: LLM summarizes the result ---
    sample = data[:5]
    summary_messages = [
        {
            "role": "system",
            "content": (
                "You are FloatChat, a helpful and friendly ocean data assistant. "
                "Write a clear, concise 2-3 sentence summary of the data result for the user. "
                "Do not list raw data values. Mention key highlights (e.g. temperature range, float count, depth range). "
                "Be conversational and informative."
            )
        },
        {
            "role": "user",
            "content": (
                f"The user asked: \"{user_message}\"\n"
                f"I ran a {query_type} query with args {args}.\n"
                f"It returned {count} observation rows. Sample (first 5): {sample}"
            )
        }
    ]

    summary_response = client.chat.completions.create(
        model=MODEL,
        messages=summary_messages,
        temperature=0.7
    )
    answer = summary_response.choices[0].message.content.strip()

    return {
        "answer": answer,
        "data": data[:1000],   # cap at 1000 rows for frontend rendering
        "plot_type": plot_type
    }


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print("Testing process_chat_query('Show me salinity in the Arabian Sea')...")
    result = process_chat_query("Show me salinity in the Arabian Sea")
    print("\n--- Answer ---")
    print(result["answer"])
    print(f"\nData rows : {len(result['data'])}")
    print(f"Plot type : {result['plot_type']}")
