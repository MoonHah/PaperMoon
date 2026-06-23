"""对话历史端点：列表/详情/删除 + 多租户隔离。经 /agent/run 落库（用假 LLM 图）。"""

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

import app.agent.graph_agent as graph_agent
from app.agent.graph_agent import build_agent_graph


@pytest.fixture(autouse=True)
def _fake_agent_graph(monkeypatch):
    # 假 LLM 图替换懒加载单例，避免真实 ChatOpenAI（同 test_agent.py）。
    fake = GenericFakeChatModel(messages=iter([AIMessage(content="[FAKE] answer")]))
    monkeypatch.setattr(graph_agent, "_graph", build_agent_graph(llm=fake))


def _auth_headers(anon_client: TestClient, email: str) -> dict:
    creds = {"email": email, "password": "secret123"}
    anon_client.post("/api/v1/auth/register", json=creds)
    token = anon_client.post("/api/v1/auth/login", json=creds).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_conversation_lifecycle(client: TestClient):
    # 跑一次 agent → 落一段会话
    sid = client.post("/api/v1/agent/run", json={"user_query": "什么是 RAG"}).json()["session_id"]
    assert sid

    convs = client.get("/api/v1/conversations").json()
    assert any(c["conversation_id"] == sid and c["title"] for c in convs)

    detail = client.get(f"/api/v1/conversations/{sid}").json()
    assert detail["messages"][0]["role"] == "user"
    assert detail["messages"][0]["content"] == "什么是 RAG"
    assert detail["messages"][1]["role"] == "assistant"

    assert client.delete(f"/api/v1/conversations/{sid}").status_code == 204
    assert client.get(f"/api/v1/conversations/{sid}").status_code == 404


def test_conversation_isolation(anon_client: TestClient):
    a = _auth_headers(anon_client, "a@conv.com")
    b = _auth_headers(anon_client, "b@conv.com")
    sid = anon_client.post(
        "/api/v1/agent/run", json={"user_query": "hi"}, headers=a
    ).json()["session_id"]

    assert anon_client.get("/api/v1/conversations", headers=b).json() == []
    assert anon_client.get(f"/api/v1/conversations/{sid}", headers=b).status_code == 404
    assert anon_client.delete(f"/api/v1/conversations/{sid}", headers=b).status_code == 404
    # A 仍在
    assert len(anon_client.get("/api/v1/conversations", headers=a).json()) == 1
