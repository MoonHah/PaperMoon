"""
Standalone tests for the model-service FastAPI app.

These tests are completely independent of the main papermoon app.
Run from model_service/ directory: cd model_service && python -m pytest
"""

from fastapi.testclient import TestClient


# ── /health ──────────────────────────────────────────────────────────────────

def test_health_returns_200(model_client: TestClient):
    assert model_client.get("/health").status_code == 200


def test_health_response_shape(model_client: TestClient):
    data = model_client.get("/health").json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "version" in data


# ── /ready ───────────────────────────────────────────────────────────────────

def test_ready_returns_200(model_client: TestClient):
    assert model_client.get("/ready").status_code == 200


def test_ready_response_shape(model_client: TestClient):
    data = model_client.get("/ready").json()
    assert "status" in data
    assert "openai" in data
    assert isinstance(data["status"], str)


# ── /generate ────────────────────────────────────────────────────────────────

def test_generate_missing_body_returns_422(model_client: TestClient):
    assert model_client.post("/generate", json={}).status_code == 422


def test_generate_success(model_client: TestClient, mock_openai):
    response = model_client.post(
        "/generate",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert isinstance(data["content"], str)
    assert len(data["content"]) > 0


def test_generate_returns_502_on_openai_failure(model_client: TestClient, failing_openai):
    response = model_client.post(
        "/generate",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert response.status_code == 502


# ── /embed ───────────────────────────────────────────────────────────────────

def test_embed_missing_body_returns_422(model_client: TestClient):
    assert model_client.post("/embed", json={}).status_code == 422


def test_embed_success(model_client: TestClient, mock_openai):
    response = model_client.post("/embed", json={"text": "Hello world"})
    assert response.status_code == 200
    data = response.json()
    assert "embedding" in data
    assert isinstance(data["embedding"], list)
    assert len(data["embedding"]) > 0


def test_embed_returns_502_on_openai_failure(model_client: TestClient, failing_openai):
    response = model_client.post("/embed", json={"text": "test"})
    assert response.status_code == 502
