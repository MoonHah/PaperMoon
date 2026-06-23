import io
from pathlib import Path

from fastapi.testclient import TestClient


def _auth_headers(anon_client: TestClient, email: str) -> dict:
    creds = {"email": email, "password": "secret123"}
    anon_client.post("/api/v1/auth/register", json=creds)
    token = anon_client.post("/api/v1/auth/login", json=creds).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_documents_are_isolated_per_user(anon_client: TestClient):
    # 用户 A 上传文档；用户 B 既看不到、也无法按 id 访问 → 多租户隔离
    a = _auth_headers(anon_client, "a@iso.com")
    b = _auth_headers(anon_client, "b@iso.com")

    up = anon_client.post(
        "/api/v1/documents/upload", files=[_txt_file(content="A's secret", name="a.txt")], headers=a
    ).json()
    a_doc_id = up["document_id"]

    # B 的列表为空
    assert anon_client.get("/api/v1/documents/", headers=b).json() == []
    # B 直接拿 A 的 doc_id → 404
    assert anon_client.get(f"/api/v1/documents/{a_doc_id}", headers=b).status_code == 404
    assert anon_client.get(f"/api/v1/documents/{a_doc_id}/status", headers=b).status_code == 404
    # A 自己能看到
    assert len(anon_client.get("/api/v1/documents/", headers=a).json()) == 1


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
    # 内容不同 → 两条独立记录（内容相同会被去重，见下方 test_duplicate_content_is_deduplicated）
    client.post("/api/v1/documents/upload", files=[_txt_file(content="AAA", name="a.txt")])
    client.post("/api/v1/documents/upload", files=[_txt_file(content="BBB", name="b.txt")])
    docs = client.get("/api/v1/documents/").json()
    assert len(docs) == 2
    filenames = {d["filename"] for d in docs}
    assert filenames == {"a.txt", "b.txt"}


def test_duplicate_content_is_deduplicated(client: TestClient):
    # 相同内容上传两次（哪怕文件名不同）：按内容指纹去重，第二次幂等复用第一次的 document_id
    r1 = client.post("/api/v1/documents/upload", files=[_txt_file(content="same", name="x.txt")]).json()
    r2 = client.post("/api/v1/documents/upload", files=[_txt_file(content="same", name="y.txt")]).json()
    assert r1["document_id"] == r2["document_id"]
    docs = client.get("/api/v1/documents/").json()
    assert len(docs) == 1


# ── Delete ───────────────────────────────────────────────────────────────────

def test_delete_document_removes_it(client: TestClient):
    doc_id = client.post(
        "/api/v1/documents/upload", files=[_txt_file()]
    ).json()["document_id"]

    assert client.delete(f"/api/v1/documents/{doc_id}").status_code == 204
    assert client.get(f"/api/v1/documents/{doc_id}").status_code == 404
    assert client.get("/api/v1/documents/").json() == []


def test_delete_nonexistent_returns_404(client: TestClient):
    assert client.delete("/api/v1/documents/nope").status_code == 404


def test_delete_not_owner_returns_404(anon_client: TestClient):
    a = _auth_headers(anon_client, "a@del.com")
    b = _auth_headers(anon_client, "b@del.com")
    doc_id = anon_client.post(
        "/api/v1/documents/upload", files=[_txt_file(content="A owns", name="a.txt")], headers=a
    ).json()["document_id"]

    # B 删 A 的文档 → 404，且 A 仍持有
    assert anon_client.delete(f"/api/v1/documents/{doc_id}", headers=b).status_code == 404
    assert len(anon_client.get("/api/v1/documents/", headers=a).json()) == 1


# ── Notes ────────────────────────────────────────────────────────────────────

def test_truncate_for_notes_caps_and_passes_through(monkeypatch):
    from app.core.config import settings
    from app.services import document_service

    monkeypatch.setattr(settings, "notes_max_chars", 100)
    assert len(document_service._truncate_for_notes("x" * 500)) == 100
    assert document_service._truncate_for_notes("short") == "short"

    monkeypatch.setattr(settings, "notes_max_chars", 0)  # 0 = 不截断
    assert len(document_service._truncate_for_notes("x" * 500)) == 500


def test_generate_notes_on_not_ready_doc_returns_409(client: TestClient):
    # 上传后状态 UPLOADED（worker 被 mock 不会处理）→ 笔记应 409 未就绪（AppError 照常透出，非 503）
    doc_id = client.post("/api/v1/documents/upload", files=[_txt_file()]).json()["document_id"]
    assert client.post(f"/api/v1/documents/{doc_id}/notes").status_code == 409


# ── 原件 / 分块 ───────────────────────────────────────────────────────────────

def test_get_document_file_returns_original_bytes(client: TestClient):
    doc_id = client.post(
        "/api/v1/documents/upload", files=[_txt_file(content="Hello world.")]
    ).json()["document_id"]
    resp = client.get(f"/api/v1/documents/{doc_id}/file")
    assert resp.status_code == 200
    assert resp.content == b"Hello world."


def test_get_document_file_not_owner_returns_404(anon_client: TestClient):
    a = _auth_headers(anon_client, "a@file.com")
    b = _auth_headers(anon_client, "b@file.com")
    doc_id = anon_client.post(
        "/api/v1/documents/upload", files=[_txt_file(content="A's", name="a.txt")], headers=a
    ).json()["document_id"]
    assert anon_client.get(f"/api/v1/documents/{doc_id}/file", headers=b).status_code == 404


def test_get_chunks_not_ready_returns_409(client: TestClient):
    # 上传后 UPLOADED（worker mock 不处理）→ 分块需 READY 正文 → 409
    doc_id = client.post("/api/v1/documents/upload", files=[_txt_file()]).json()["document_id"]
    assert client.get(f"/api/v1/documents/{doc_id}/chunks").status_code == 409


def test_generate_notes_returns_503_on_internal_failure(client: TestClient, monkeypatch):
    # LLM 等内部失败 → 兜成友好 503，而非裸 500
    doc_id = client.post("/api/v1/documents/upload", files=[_txt_file()]).json()["document_id"]
    from app.services import document_service

    def boom(*a, **k):
        raise RuntimeError("llm down")

    monkeypatch.setattr(document_service, "generate_notes", boom)
    assert client.post(f"/api/v1/documents/{doc_id}/notes").status_code == 503
