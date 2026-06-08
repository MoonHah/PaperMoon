import json

from fastapi.testclient import TestClient

from tests.conftest import InMemoryVectorStore


def test_chat_empty_kb_returns_400(client: TestClient):
    """Vector store is empty → rag_service raises ValueError → 400."""
    response = client.post("/api/v1/chat", json={"query": "What is Python?"})
    assert response.status_code == 400


def test_chat_response_shape(client: TestClient, mock_store: InMemoryVectorStore):
    mock_store.upsert(
        document_id="doc-1",
        filename="python.txt",
        chunks=["Python is a programming language."],
        embeddings=[[0.1] * 256],
    )

    response = client.post("/api/v1/chat", json={"query": "What is Python?"})
    assert response.status_code == 200

    data = response.json()
    assert "answer" in data
    assert "retrieved_chunks" in data
    assert isinstance(data["answer"], str)
    assert isinstance(data["retrieved_chunks"], list)


def test_chat_returns_retrieved_chunks(client: TestClient, mock_store: InMemoryVectorStore):
    mock_store.upsert(
        document_id="doc-2",
        filename="go.txt",
        chunks=["Go is a compiled language by Google.", "Go has goroutines for concurrency."],
        embeddings=[[0.2] * 256, [0.3] * 256],
    )

    data = client.post("/api/v1/chat", json={"query": "Tell me about Go", "top_k": 2}).json()
    assert len(data["retrieved_chunks"]) > 0


def test_chat_answer_is_non_empty_string(client: TestClient, mock_store: InMemoryVectorStore):
    mock_store.upsert(
        document_id="doc-3",
        filename="test.txt",
        chunks=["Some relevant content here."],
        embeddings=[[0.5] * 256],
    )

    data = client.post("/api/v1/chat", json={"query": "relevant content"}).json()
    assert len(data["answer"]) > 0


# ── 流式端点测试 ─────────────────────────────────────────────────────────────

def test_stream_chat_empty_kb_returns_400(client: TestClient):
    """向量库为空时，提前校验应返回 400，而不是 200 后流中断。"""
    response = client.post("/api/v1/chat?stream=true", json={"query": "test"})
    assert response.status_code == 400


def test_stream_chat_content_type_is_sse(client: TestClient, mock_store: InMemoryVectorStore):
    """流式响应的 Content-Type 必须是 text/event-stream。"""
    mock_store.upsert(
        document_id="doc-s1",
        filename="sse.txt",
        chunks=["SSE test content."],
        embeddings=[[0.1] * 256],
    )
    response = client.post("/api/v1/chat?stream=true", json={"query": "test"})
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


def test_stream_chat_sse_format(client: TestClient, mock_store: InMemoryVectorStore):
    """每一块都是 'data: {...}\\n\\n' 格式，最后一块是 'data: [DONE]\\n\\n'。"""
    mock_store.upsert(
        document_id="doc-s2",
        filename="format.txt",
        chunks=["Format test content."],
        embeddings=[[0.2] * 256],
    )
    response = client.post("/api/v1/chat?stream=true", json={"query": "test"})
    events = [e for e in response.text.split("\n\n") if e]

    assert events[-1] == "data: [DONE]"
    for event in events[:-1]:
        assert event.startswith("data: ")
        payload = json.loads(event[len("data: "):])
        assert "token" in payload


def test_stream_chat_tokens_reassemble_to_full_answer(client: TestClient, mock_store: InMemoryVectorStore):
    """把所有 token 拼接后，应该包含 MockLLMService 的标志字符串 [MOCK]。"""
    mock_store.upsert(
        document_id="doc-s3",
        filename="mock.txt",
        chunks=["Mock content for streaming."],
        embeddings=[[0.3] * 256],
    )
    response = client.post("/api/v1/chat?stream=true", json={"query": "test"})
    tokens = [
        json.loads(e[len("data: "):])["token"]
        for e in response.text.split("\n\n")
        if e.startswith("data: ") and e != "data: [DONE]"
    ]
    assert len(tokens) > 0
    assert "[MOCK]" in "".join(tokens)
