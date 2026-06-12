"""
Agent integration tests.

search_documents is the default tool and works with the mock vector store.
summarize_document/compare_documents use SessionLocal directly; we patch it to SQLite
so tests stay isolated and don't attempt a real PostgreSQL connection.
"""

import pytest
from fastapi.testclient import TestClient

import app.agent.tools as _tools_mod
from tests.conftest import _TestSession


@pytest.fixture(autouse=True)
def _patch_tools_session(monkeypatch):
    """Patch SessionLocal inside agent/tools.py to use SQLite."""
    monkeypatch.setattr(_tools_mod, "SessionLocal", _TestSession)


def test_agent_run_returns_200(client: TestClient):
    response = client.post("/api/v1/agent/run", json={"user_query": "What is Python?"})
    assert response.status_code == 200


def test_agent_response_shape(client: TestClient):
    data = client.post("/api/v1/agent/run", json={"user_query": "What is Python?"}).json()
    assert "final_answer" in data
    assert "selected_tool" in data
    assert "intermediate_steps" in data
    assert isinstance(data["intermediate_steps"], list)
    assert len(data["intermediate_steps"]) > 0


def test_agent_default_query_uses_search_tool(client: TestClient):
    data = client.post("/api/v1/agent/run", json={"user_query": "Tell me about databases"}).json()
    # loop 架构下 selected_tool 是结束状态；工具体现在 intermediate_steps 的 action
    assert "search_documents" in [s["action"] for s in data["intermediate_steps"]]


def test_agent_summarize_keyword_selects_summarize_tool(client: TestClient):
    data = client.post(
        "/api/v1/agent/run",
        json={"user_query": "请总结这篇文章", "document_ids": ["any-doc-id"]},
    ).json()
    # 即使工具执行失败，步骤里仍记录了被选中的工具
    assert "summarize_document" in [s["action"] for s in data["intermediate_steps"]]


def test_agent_compare_keyword_selects_compare_tool(client: TestClient):
    data = client.post(
        "/api/v1/agent/run",
        json={"user_query": "对比这两篇文档", "document_ids": ["id-1", "id-2"]},
    ).json()
    assert "compare_documents" in [s["action"] for s in data["intermediate_steps"]]


def test_agent_intermediate_steps_have_required_fields(client: TestClient):
    data = client.post("/api/v1/agent/run", json={"user_query": "hello"}).json()
    for step in data["intermediate_steps"]:
        assert "step" in step
        assert "action" in step
        assert "status" in step


def test_agent_citations_is_list(client: TestClient):
    data = client.post("/api/v1/agent/run", json={"user_query": "anything"}).json()
    assert isinstance(data.get("citations", []), list)
