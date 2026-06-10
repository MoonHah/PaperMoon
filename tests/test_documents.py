import io
from pathlib import Path

from fastapi.testclient import TestClient


def _txt_file(content: str = "Hello world.", name: str = "test.txt"):
    return ("file", (name, content.encode(), "text/plain"))


def _md_file(name: str = "notes.md"):
    return ("file", (name, b"# Title\n\nContent.", "text/markdown"))


def _pdf_file(name: str = "sample.pdf"):
    pdf_path = Path(__file__).parent / "fixtures" / name
    return ("file", (name, pdf_path.read_bytes(), "application/pdf"))


# ── Upload ───────────────────────────────────────────────────────────────────

def test_upload_txt_returns_200(client: TestClient):
    response = client.post("/api/v1/documents/upload", files=[_txt_file()])
    assert response.status_code == 200


def test_upload_md_returns_200(client: TestClient):
    response = client.post("/api/v1/documents/upload", files=[_md_file()])
    assert response.status_code == 200


def test_upload_response_shape(client: TestClient):
    data = client.post("/api/v1/documents/upload", files=[_txt_file()]).json()
    assert "document_id" in data
    assert "task_id" in data
    assert "filename" in data
    assert data["status"] == "UPLOADED"


def test_upload_pdf_returns_200(client: TestClient):
    response = client.post("/api/v1/documents/upload", files=[_pdf_file()])
    assert response.status_code == 200
    data = response.json()
    assert "document_id" in data
    assert data["status"] == "UPLOADED"


def test_upload_unsupported_format_returns_400(client: TestClient):
    response = client.post(
        "/api/v1/documents/upload",
        files=[("file", ("report.docx", b"fake docx content", "application/octet-stream"))],
    )
    assert response.status_code == 400


def test_upload_too_large_returns_413(client: TestClient, monkeypatch):
    from app.core.config import settings

    # Set limit to 0 MB so any non-empty file exceeds it
    monkeypatch.setattr(settings, "max_file_size_mb", 0)
    response = client.post("/api/v1/documents/upload", files=[_txt_file()])
    assert response.status_code == 413


def test_upload_non_utf8_returns_400(client: TestClient):
    response = client.post(
        "/api/v1/documents/upload",
        files=[("file", ("binary.txt", bytes(range(128, 200)), "text/plain"))],
    )
    assert response.status_code == 400


# ── List ─────────────────────────────────────────────────────────────────────

def test_list_documents_empty(client: TestClient):
    response = client.get("/api/v1/documents/")
    assert response.status_code == 200
    assert response.json() == []


def test_list_documents_after_upload(client: TestClient):
    client.post("/api/v1/documents/upload", files=[_txt_file()])
    data = client.get("/api/v1/documents/").json()
    assert len(data) == 1
    assert data[0]["status"] == "UPLOADED"


# ── Get by ID ────────────────────────────────────────────────────────────────

def test_get_document_not_found_returns_404(client: TestClient):
    response = client.get("/api/v1/documents/nonexistent-id")
    assert response.status_code == 404


def test_get_document_by_id_returns_correct_fields(client: TestClient):
    upload = client.post("/api/v1/documents/upload", files=[_txt_file()]).json()
    doc_id = upload["document_id"]

    response = client.get(f"/api/v1/documents/{doc_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == doc_id
    assert data["filename"] == "test.txt"
    assert data["file_type"] == ".txt"
    assert data["status"] == "UPLOADED"


def test_two_uploads_are_independent(client: TestClient):
    client.post("/api/v1/documents/upload", files=[_txt_file(name="a.txt")])
    client.post("/api/v1/documents/upload", files=[_txt_file(name="b.txt")])
    docs = client.get("/api/v1/documents/").json()
    assert len(docs) == 2
    filenames = {d["filename"] for d in docs}
    assert filenames == {"a.txt", "b.txt"}
