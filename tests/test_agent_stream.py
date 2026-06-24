"""流式 agent 端点 /agent/run/stream：SSE 格式 + final 事件 + [DONE] 收尾 + 流末落库。

用假 LLM 图（同 test_agent.py），不触发真实 ChatOpenAI。
"""

import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

import app.agent.graph_agent as graph_agent
from app.agent.graph_agent import build_agent_graph


@pytest.fixture(autouse=True)
def _fake_agent_graph(monkeypatch):
    fake = GenericFakeChatModel(messages=iter([AIMessage(content="[FAKE] answer")]))
    monkeypatch.setattr(graph_agent, "_graph", build_agent_graph(llm=fake))


def _events(text: str) -> list[dict]:
    """从 SSE 文本里解析出 JSON 事件（跳过 [DONE] 哨兵）。"""
    out = []
    for part in text.split("\n\n"):
        line = part.strip()
        if line.startswith("data:"):
            data = line[len("data:") :].strip()
            if data and data != "[DONE]":
                out.append(json.loads(data))
    return out


def test_stream_returns_sse_and_final(client: TestClient):
    resp = client.post("/api/v1/agent/run/stream", json={"user_query": "什么是 RAG"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "[DONE]" in resp.text

    final = [e for e in _events(resp.text) if e.get("type") == "final"]
    assert len(final) == 1
    assert final[0]["final_answer"] == "[FAKE] answer"
    assert final[0]["session_id"]


def test_stream_persists_conversation(client: TestClient):
    resp = client.post("/api/v1/agent/run/stream", json={"user_query": "落库测试"})
    sid = next(e for e in _events(resp.text) if e.get("type") == "final")["session_id"]

    # 流结束（[DONE] 前）已落库 → 历史列表/详情能查到
    convs = client.get("/api/v1/conversations").json()
    assert any(c["conversation_id"] == sid for c in convs)
    detail = client.get(f"/api/v1/conversations/{sid}").json()
    assert detail["messages"][0]["content"] == "落库测试"
    assert detail["messages"][1]["role"] == "assistant"
    assert detail["messages"][1]["content"] == "[FAKE] answer"
