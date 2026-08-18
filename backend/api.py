"""
backend/api.py
==============
FastAPI server serving as the bridge between the React frontend and the ocean data pipeline.
"""

import os
import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

# Ensure project root is on sys.path when executed directly as `python backend/api.py`
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.rag import process_chat_query
from backend.queries import get_dataset_metadata
from backend.vector_store import init_vector_store
from backend.schemas.query import AnalyticsSummary

# Configure logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("floatchat_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager: initialize vector store and metadata on startup."""
    logger.info("Initializing FloatChat API services...")
    try:
        init_vector_store()
    except Exception as e:
        logger.warning(f"Vector store initialization deferred: {e}")
    yield
    logger.info("Shutting down FloatChat API services.")


app = FastAPI(title="FloatChat API", version="1.0.0", lifespan=lifespan)

# Configure CORS using environment variable
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
origins = [frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str
    data: List[Dict[str, Any]]
    plot_type: str
    intent: Dict[str, Any]
    analytics: AnalyticsSummary


class DatasetMetadataResponse(BaseModel):
    status: str
    earliest_date: Optional[str] = None
    latest_date: Optional[str] = None
    total_observations: int = 0
    total_floats: int = 0
    total_profiles: int = 0
    min_lat: Optional[float] = None
    max_lat: Optional[float] = None
    min_lon: Optional[float] = None
    max_lon: Optional[float] = None
    min_depth: Optional[float] = None
    max_depth: Optional[float] = None


@app.get("/")
def root():
    """Root status and navigation endpoint."""
    return {
        "service": "FloatChat Oceanographic Intelligence API",
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs",
        "health": "/health",
        "frontend": "http://localhost:5173"
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "FloatChat API"}


@app.get("/dataset/metadata", response_model=DatasetMetadataResponse)
def get_metadata_endpoint():
    """Return dataset spatial, temporal, and count metadata."""
    try:
        meta = get_dataset_metadata()
        return DatasetMetadataResponse(**meta)
    except Exception as e:
        logger.error(f"Error fetching dataset metadata: {e}", exc_info=True)
        return DatasetMetadataResponse(status="unavailable")


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """
    Process a natural language query and return LLM response, dataset payload,
    intent visualization specs, and analytics summary.
    """
    if not req.message or not req.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty."
        )

    try:
        result = process_chat_query(req.message.strip())
        return ChatResponse(
            answer=result["answer"],
            data=result["data"],
            plot_type=result["plot_type"],
            intent=result.get("intent", {}),
            analytics=result.get("analytics", AnalyticsSummary())
        )
    except ValueError as e:
        logger.error(f"Configuration or validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI query service is temporarily unconfigured or unavailable."
        )
    except Exception as e:
        logger.error(f"Unhandled error processing query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your ocean data request. Please try again."
        )


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)

