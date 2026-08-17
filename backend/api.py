"""
backend/api.py
==============
FastAPI server serving as the bridge between the React frontend and the RAG pipeline.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from backend.rag import process_chat_query
from backend.vector_store import init_vector_store

app = FastAPI(title="FloatChat API")

# Configure CORS for the frontend (which usually runs on localhost:5173 for Vite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all in dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    """Initialize vector DB on startup."""
    init_vector_store()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    answer: str
    data: List[Dict[str, Any]]
    plot_type: str

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """
    Process a natural language query and return the LLM summary + raw data.
    """
    try:
        result = process_chat_query(req.message)
        return ChatResponse(
            answer=result["answer"],
            data=result["data"],
            plot_type=result["plot_type"]
        )
    except ValueError as e:
        # e.g., missing API key
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print("Error processing query:", e)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
