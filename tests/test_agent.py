"""Agent 端点集成测试：验证 POST /api/v1/agent/run 的 HTTP 契约。

Agent 内部逻辑（多轮记忆 / 引用回收 / 历史修剪）由 test_graph_agent.py 覆盖；
这里只用假模型图打通端点，避免真实 ChatOpenAI，验证响应 schema。
"""

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

import app.agent.graph_agent as graph_agent
from app.agent.graph_agent import build_agent_graph


@pytest.fixture(autouse=True)
def _fake_agent_graph(monkeypatch):
    # 用假 LLM 图替换懒加载单例：端点 → graph_agent.run → 此图，不触发真实 ChatOpenAI。
    fake = GenericFakeChatModel(messages=iter([AIMessage(content="[FAKE] answer")]))
    monkeypatch.setattr(graph_agent, "_graph", build_agent_graph(llm=fake))


def test_agent_run_returns_200(client: TestClient):
    resp = client.post("/api/v1/agent/run", json={"user_query": "什么是 RAG？"})
    assert resp.status_code == 200


def test_agent_response_shape(client: TestClient):
    data = client.post("/api/v1/agent/run", json={"user_query": "hi"}).json()
    assert data["final_answer"] == "[FAKE] answer"
    assert "selected_tool" in data
    assert isinstance(data["intermediate_steps"], list)
    assert isinstance(data.get("citations", []), list)
    assert data["session_id"]  # langgraph 总会返回 session_id


def test_agent_reuses_session_id(client: TestClient):
    # 带上一轮的 session_id 续聊，服务端应回显同一个
    sid = "fixed-session-1"
    data = client.post(
        "/api/v1/agent/run",
        json={"user_query": "hi", "session_id": sid},
    ).json()
    assert data["session_id"] == sid
