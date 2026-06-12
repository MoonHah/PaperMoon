from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

import app.agent.graph_agent as graph_agent
from app.agent.graph_agent import build_agent_graph
from app.agent.schemas import AgentRunRequest


def test_same_thread_shares_history():
    fake = GenericFakeChatModel(messages=iter([
        AIMessage(content="answer-1"),
        AIMessage(content="answer-2"),
    ]))
    graph = build_agent_graph(llm=fake)
    # 内联字面量可被双向推断，但赋给变量必须显式标注 RunnableConfig（否则 pyright 推成宽泛 dict）
    cfg: RunnableConfig = {"configurable": {"thread_id": "t1"}}

    # 挂了 checkpointer 后 thread_id 必填——每次 invoke 都要带 config
    graph.invoke({"messages": [HumanMessage(content="问题一")]}, config=cfg)
    result = graph.invoke({"messages": [HumanMessage(content="问题二")]}, config=cfg)

    # 第二轮的 state 含全部 4 条消息（Human1, AI1, Human2, AI2）→ 历史共享成立
    assert len(result["messages"]) == 4


def test_different_threads_are_isolated():
    fake = GenericFakeChatModel(messages=iter([
        AIMessage(content="answer-1"),
        AIMessage(content="answer-2"),
    ]))
    graph = build_agent_graph(llm=fake)   # 一张图一个 checkpointer，按 thread_id 分隔间
    cfg_1: RunnableConfig = {"configurable": {"thread_id": "t1"}}
    cfg_2: RunnableConfig = {"configurable": {"thread_id": "t2"}}

    graph.invoke(
        {"messages": [HumanMessage(content="t1 的问题")]},
        config=cfg_1,
    )

    result = graph.invoke(
        {"messages": [HumanMessage(content="t2 的问题")]},
        config=cfg_2,
    )

    # t2 只有自己的 Human + AI（== 2），看不到 t1 的历史 → 隔离成立
    assert len(result["messages"]) == 2


class _RecordingLLM:
    """包装假模型，记录每次 invoke 收到的消息条数——用于验证历史修剪。"""

    def __init__(self, inner):
        self._inner = inner
        self.seen_lengths: list[int] = []

    def invoke(self, messages):
        self.seen_lengths.append(len(messages))
        return self._inner.invoke(messages)


def test_history_window_trims_llm_input_but_keeps_full_state(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "agent_history_window", 4)   # 窗口收紧到 4 条便于观察

    fake = GenericFakeChatModel(messages=iter(
        [AIMessage(content=f"answer-{i}") for i in range(5)]
    ))
    recorder = _RecordingLLM(fake)
    graph = build_agent_graph(llm=recorder)
    cfg: RunnableConfig = {"configurable": {"thread_id": "t-trim"}}

    result: dict = {}
    for i in range(5):   # 聊 5 轮 → 完整历史 10 条，远超窗口
        result = graph.invoke({"messages": [HumanMessage(content=f"问题{i}")]}, config=cfg)

    # 存储侧：checkpointer 保留完整历史（10 条），修剪不动它
    assert len(result["messages"]) == 10
    # LLM 侧：每次 invoke 看到的消息数不超过窗口
    assert max(recorder.seen_lengths) <= 4


def test_run_returns_and_reuses_session_id(monkeypatch):
    fake = GenericFakeChatModel(messages=iter([
        AIMessage(content="answer-1"),
        AIMessage(content="answer-2"),
    ]))
    # 把懒加载单例换成假模型图，绕开真实 ChatOpenAI；pytest 结束后自动还原
    monkeypatch.setattr(graph_agent, "_graph", build_agent_graph(llm=fake))

    # 第一次不传 session_id → 服务端生成并返回
    resp1 = graph_agent.run(AgentRunRequest(user_query="第一问"))
    assert resp1.session_id is not None

    # 带着它续聊 → 返回同一个 id，且第二轮能看到第一轮的回答（历史共享）
    resp2 = graph_agent.run(AgentRunRequest(user_query="第二问", session_id=resp1.session_id))
    assert resp2.session_id == resp1.session_id
    assert resp2.final_answer == "answer-2"
