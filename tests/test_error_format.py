"""
Verify that ALL error responses follow the unified error envelope:
  {"error_code": str, "message": str, "details": dict}

This tests our custom exception handlers in app/core/errors.py.
"""

from fastapi.testclient import TestClient


def _assert_error_envelope(data: dict) -> None:
    assert "error_code" in data, f"Missing 'error_code' in: {data}"
    assert "message" in data, f"Missing 'message' in: {data}"
    assert isinstance(data["error_code"], str)
    assert isinstance(data["message"], str)


def test_404_error_has_envelope(client: TestClient):
    response = client.get("/api/v1/documents/nonexistent-id")
    assert response.status_code == 404
    _assert_error_envelope(response.json())


def test_400_upload_unsupported_format_has_envelope(client: TestClient):
    response = client.post(
        "/api/v1/documents/upload",
        files=[("file", ("report.docx", b"data", "application/octet-stream"))],
    )
    assert response.status_code == 400
    _assert_error_envelope(response.json())


def test_400_chat_empty_kb_has_envelope(client: TestClient):
    response = client.post("/api/v1/chat", json={"query": "anything"})
    assert response.status_code == 400
    _assert_error_envelope(response.json())


def test_422_missing_required_field_has_envelope(client: TestClient):
    # ChatRequest requires 'query'; sending empty object triggers 422
    response = client.post("/api/v1/chat", json={})
    assert response.status_code == 422
    data = response.json()
    _assert_error_envelope(data)
    assert data["error_code"] == "VALIDATION_ERROR"


def test_404_error_code_contains_status(client: TestClient):
    response = client.get("/api/v1/documents/no-such-doc")
    data = response.json()
    assert "404" in data["error_code"]


def test_422_empty_filename_has_envelope(client: TestClient):
    # Empty filename triggers FastAPI's multipart validation (422), not our 400 check.
    # The important thing is the response still follows our error envelope.
    response = client.post(
        "/api/v1/documents/upload",
        files=[("file", ("", b"data", "text/plain"))],
    )
    assert response.status_code == 422
    data = response.json()
    _assert_error_envelope(data)
    assert data["error_code"] == "VALIDATION_ERROR"
