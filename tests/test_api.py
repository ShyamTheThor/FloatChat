"""
tests/test_api.py
=================
Integration tests for FastAPI endpoints.
"""

from fastapi.testclient import TestClient
from backend.api import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dataset_metadata_endpoint():
    response = client.get("/dataset/metadata")
    assert response.status_code == 200
    assert "status" in response.json()


def test_chat_endpoint_empty_message():
    response = client.post("/chat", json={"message": ""})
    assert response.status_code == 400
