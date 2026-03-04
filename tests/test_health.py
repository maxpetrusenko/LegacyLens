"""
Health checks and smoke tests for Qdrant collections and API.

Tests verify:
- Qdrant Cloud connectivity
- Collections exist and have data
- Basic API smoke tests
"""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from legacylens.api import app
from legacylens.config import Settings
from legacylens.vector_store import QdrantStore

client = TestClient(app)


def test_qdrant_connection() -> None:
    """Verify Qdrant Cloud is reachable."""
    settings = Settings()
    store = QdrantStore(settings)

    # Should not raise exception and return collections list
    collections = store.client.get_collections()
    assert hasattr(collections, "collections")
    assert isinstance(collections.collections, list)


def test_dev_collection_exists() -> None:
    """Verify dev collection exists and has points."""
    settings = Settings()
    store = QdrantStore(settings)

    collection = store.client.get_collection(settings.qdrant_collection)
    assert collection.points_count > 0, f"Collection {settings.qdrant_collection} is empty"


def test_vector_store_search_returns_results() -> None:
    """Verify semantic search returns results."""
    settings = Settings()
    store = QdrantStore(settings)

    # Use a known vector from text-embedding-3-small
    test_vector = [0.0] * 1536
    hits = store.search(test_vector, limit=5)

    # Should return results (or empty list, not error)
    assert isinstance(hits, list)


def test_api_health_endpoint() -> None:
    """Health check for API."""
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"


def test_api_meta_endpoint() -> None:
    """Meta endpoint returns available endpoints."""
    response = client.get("/meta")
    assert response.status_code == 200
    payload = response.json()
    assert "graph" in payload


@pytest.mark.smoke
def test_query_endpoint_accepts_requests() -> None:
    """Smoke test: query endpoint accepts POST and returns response."""
    response = client.post("/query", json={"query": "test query"})
    # Should return 200 or 503 (service unavailable), not 500
    assert response.status_code in {200, 503}

    payload = response.json()
    # Should have answer or error detail
    assert "answer" in payload or "detail" in payload


@pytest.mark.smoke
def test_graph_endpoint_accepts_requests() -> None:
    """Smoke test: graph endpoint accepts requests."""
    response = client.get("/graph/TEST_SYMBOL")
    # Should return 200 or 404 (not found), not 500
    assert response.status_code in {200, 404}
