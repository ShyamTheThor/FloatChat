"""
backend/vector_store.py
=======================
Initializes ChromaDB and stores metadata (regions, parameters, float summaries)
for the RAG layer to access.
"""

from __future__ import annotations

import os
from pathlib import Path

import chromadb
from chromadb.config import Settings

# Keep ChromaDB in the data directory
CHROMA_DB_DIR = Path(__file__).parent.parent / "data" / "chroma"
COLLECTION_NAME = "argo_metadata"

# Pre-defined metadata to embed (based on docs/schema.md and README.md)
METADATA_DOCUMENTS = [
    {
        "id": "region_arabian_sea",
        "text": "The Arabian Sea is a region of the northern Indian Ocean bounded on the north by Pakistan and Iran, on the west by the Gulf of Aden, Guardafui Channel and the Arabian Peninsula, and on the east by India. Its bounding box is min_lat=5, max_lat=25, min_lon=55, max_lon=80.",
        "metadata": {"type": "region", "min_lat": 5.0, "max_lat": 25.0, "min_lon": 55.0, "max_lon": 80.0, "name": "Arabian Sea"}
    },
    {
        "id": "region_bay_of_bengal",
        "text": "The Bay of Bengal is the northeastern part of the Indian Ocean, bounded on the west and northwest by India, on the north by Bangladesh, and on the east by Myanmar and the Andaman and Nicobar Islands of India. Its bounding box is min_lat=5, max_lat=22, min_lon=80, max_lon=100.",
        "metadata": {"type": "region", "min_lat": 5.0, "max_lat": 22.0, "min_lon": 80.0, "max_lon": 100.0, "name": "Bay of Bengal"}
    },
    {
        "id": "region_full_indian_ocean",
        "text": "The Indian Ocean is the third-largest of the world's five oceanic divisions. For our tracking purposes, the full Indian Ocean bounding box is min_lat=-10, max_lat=25, min_lon=40, max_lon=105.",
        "metadata": {"type": "region", "min_lat": -10.0, "max_lat": 25.0, "min_lon": 40.0, "max_lon": 105.0, "name": "Indian Ocean"}
    },
    {
        "id": "region_south_indian_ocean",
        "text": "The South Indian Ocean is the portion of the Indian Ocean south of the equator. The bounding box is min_lat=-60, max_lat=-10, min_lon=20, max_lon=120.",
        "metadata": {"type": "region", "min_lat": -60.0, "max_lat": -10.0, "min_lon": 20.0, "max_lon": 120.0, "name": "South Indian Ocean"}
    },
    {
        "id": "param_temperature",
        "text": "Temperature measures the in-situ ocean water temperature in degrees Celsius (°C). Valid ranges are typically -2.0 to 35.0 °C. The warmest waters are usually found near the equator or in shallow seas.",
        "metadata": {"type": "parameter", "name": "temperature", "unit": "degree_Celsius"}
    },
    {
        "id": "param_salinity",
        "text": "Salinity measures the practical salinity of the ocean water in psu. Valid ranges are typically 0.0 to 42.0 psu. High salinity means saltier water.",
        "metadata": {"type": "parameter", "name": "salinity", "unit": "psu"}
    },
    {
        "id": "param_depth",
        "text": "Depth is the distance below the ocean surface, measured in metres (m). The upper mixed layer is typically 0 to 200 m.",
        "metadata": {"type": "parameter", "name": "depth_m", "unit": "metre"}
    }
]

def get_chroma_client():
    """Get the local ChromaDB client."""
    return chromadb.PersistentClient(path=str(CHROMA_DB_DIR))

def init_vector_store():
    """Initialize the ChromaDB collection and load metadata if it doesn't exist."""
    try:
        client = get_chroma_client()
        collection = client.get_or_create_collection(name=COLLECTION_NAME)
        
        # Check if we need to insert data
        if collection.count() == 0:
            print(f"Initializing Vector DB in {CHROMA_DB_DIR}...")
            ids = [doc["id"] for doc in METADATA_DOCUMENTS]
            texts = [doc["text"] for doc in METADATA_DOCUMENTS]
            metadatas = [doc["metadata"] for doc in METADATA_DOCUMENTS]
            
            collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas
            )
            print(f"Inserted {len(METADATA_DOCUMENTS)} metadata documents into ChromaDB.")
        else:
            print(f"Vector DB already initialized with {collection.count()} documents.")
    except Exception as e:
        print(f"[vector_store.py] Warning: Vector store init deferred/failed: {e}")

def search_metadata(query: str, n_results: int = 2) -> list[dict]:
    """
    Search the metadata collection for context relevant to the query.
    Returns a list of dicts with 'text' and 'metadata'.
    """
    try:
        client = get_chroma_client()
        collection = client.get_collection(name=COLLECTION_NAME)
        
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        context = []
        if results and "documents" in results and results["documents"]:
            for idx in range(len(results["documents"][0])):
                context.append({
                    "text": results["documents"][0][idx],
                    "metadata": results["metadatas"][0][idx]
                })
        return context
    except Exception as e:
        print(f"[vector_store.py] Warning: Metadata search failed: {e}")
        return []

if __name__ == "__main__":
    # Test initialization
    init_vector_store()
    print("Test search for 'salinity in the Arabian Sea':")
    res = search_metadata("salinity in the Arabian Sea", n_results=2)
    for r in res:
        print(" -", r["text"])
