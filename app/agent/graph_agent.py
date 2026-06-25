"""Agent 运行服务：run()（同步，返回完整 AgentRunResponse）/ run_stream()（SSE 流式事件）。

图构建见 graph_build，工具定义见 tool_defs。本模块只管"怎么跑图、怎么把结果翻译成对外契约"。
build_agent_graph 经本模块再导出：测试与 API 端点历来从 graph_agent 取它，保持公共入口稳定。
"""

import logging
import queue
import threading
from collections.abc import Iterator
from uuid import uuid4

from langchain_core.messages import HumanMessage, ToolMessage

from app.agent.graph_build import build_agent_graph
from app.agent.schemas import AgentRunRequest, AgentRunResponse, CitedChunk, IntermediateStep
from app.core.context import (
    reset_current_user_id,
    reset_document_scope,
    set_current_user_id,
    set_document_scope,
)

__all__ = ["run", "run_stream", "build_agent_graph", "get_agent_graph"]

logger = logging.getLogger(__name__)


# 懒加载单例：首次调用才编译图（创建 LLM 客户端），消除 import 副作用
_graph = None


def get_agent_graph():
    global _graph
    if _graph is None:
        _graph = build_agent_graph()
    return _graph


_RESULT_PREVIEW_LIMIT = 160


def _result_preview(content, limit: int = _RESULT_PREVIEW_LIMIT) -> str:
    """把工具结果压成单行短预览供轨迹展示（折叠空白 + 截断），不改动给 LLM 的原文。"""
    s = " ".join(str(content).split())
    return s if len(s) <= limit else s[:limit] + "…"


def run(request: AgentRunRequest, user_id: str) -> AgentRunResponse:
    """同步跑 LangGraph agent，返回完整 AgentRunResponse（API 契约不因后端实现而变）。

    user_id：经 contextvar 注入，供工具按用户隔离检索/列表/归属校验；
    thread_id 也用 user 命名空间，防跨用户猜 session。
    """
    session_id = request.session_id or str(uuid4())
    thread_id = f"{user_id}:{session_id}"   # 会话按用户隔离
    # 文档范围：用户勾选则限定检索/列举在这些文档内；空列表视为不限定（全部已就绪文档）。
    scope = request.document_ids or None
    token = set_current_user_id(user_id)
    scope_token = set_document_scope(scope)
    try:
        # invoke 从入口跑到 END，自动驱动 agent↔tools 循环，返回跑完的完整 state
        result = get_agent_graph().invoke(
            {"messages": [HumanMessage(content=request.user_query)]},
            config={
                "configurable": {"thread_id": thread_id},  # 绑定会话（按用户命名空间）
                "recursion_limit": 10,
                },   # 兜底防死循环（≈ 手写版 MAX_STEPS）
        )
    except Exception as e:
        return AgentRunResponse(
            final_answer="Agent 执行失败，请稍后重试。",
            selected_tool="(error)",
            intermediate_steps=[],
            error=str(e),
            session_id=session_id
        )
    finally:
        reset_document_scope(scope_token)
        reset_current_user_id(token)

    # 完整历史：Human → AI(tool_calls) → Tool → … → AI(最终答案)
    messages = result["messages"]
    last_human = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
    current_turn = messages[last_human:]

    # 按 tool_call_id 关联「发起的调用(AIMessage.tool_calls)」与「执行结果(ToolMessage)」。
    # ToolNode(handle_tool_errors=True) 失败时产出 status="error" 的 ToolMessage——据此如实标注成败，
    # 不再硬编码 "ok"；content 取单行短预览，让用户看到工具产出而不只是"调了什么"。
    tool_results = {m.tool_call_id: m for m in current_turn if isinstance(m, ToolMessage)}
    steps: list[IntermediateStep] = []
    for tc in (tc for m in current_turn for tc in (getattr(m, "tool_calls", None) or [])):
        tm = tool_results.get(tc["id"])
        steps.append(
            IntermediateStep(
                step=len(steps) + 1,
                action=tc["name"],
                detail=str(tc.get("args", {})),
                status="error" if (tm is not None and getattr(tm, "status", None) == "error") else "ok",
                result=_result_preview(tm.content) if tm is not None else "",
            )
        )

    # 从本轮 search_documents 的 ToolMessage.artifact 回收结构化引用（content_and_artifact）。
    # 按 (document_id, text) 去重：一轮内可能多次检索、命中重复片段。
    citations: list[CitedChunk] = []
    seen: set[tuple[str, str]] = set()
    for m in current_turn:
        if isinstance(m, ToolMessage) and m.name == "search_documents" and m.artifact:
            for c in m.artifact:
                key = (c["document_id"], c["text"])
                if key not in seen:
                    seen.add(key)
                    citations.append(CitedChunk(**c))

    return AgentRunResponse(
        final_answer=messages[-1].content,
        selected_tool="(final)",
        intermediate_steps=steps,
        citations=citations,
        session_id=session_id
    )


def run_stream(request: AgentRunRequest, user_id: str) -> Iterator[dict]:
    """流式跑 agent：把 graph.stream 的逐节点/逐 token 产出翻译成前端事件，实时展示推理轨迹。

    与 run() 同源（共用图 + _result_preview + 按 tool_call_id 配对 + 引用回收），区别只是
    增量产出而非跑完再回收。事件类型：
      - step_start  {step, action, detail}        —— agent 发起工具调用（前端标"运行中"）
      - step_result {step, status, result}        —— 工具执行完，如实 status + 结果预览
      - token       {text}                        —— agent 节点 LLM 的内容增量（打字机效果）
      - final       {final_answer, citations, steps, session_id}  —— 收尾（权威全文校正 + 端点落库）
      - error       {message}                     —— 执行期任何异常

    ⚠️ 为何用 worker 线程 + 队列、而非直接在本生成器里跑图：
    StreamingResponse 的同步生成器被 Starlette 用线程池逐个 next() 驱动，每次 next() 可能落在
    不同线程、各拿一份上下文拷贝。若在生成器体里 set/reset contextvar，会出两个 bug：①工具在后续
    next() 的拷贝里读不到 user_id（隔离失效）；②finally 里 reset(token) 时 token 已属于另一份上下文
    → ValueError「different Context」。故把整段图执行关进一个 worker 线程：contextvar 在该线程内
    设一次、贯穿所有节点/工具、同线程 reset；本生成器只从队列搬运事件，不碰 contextvar。
    落库不在此处（保持 agent 与会话存储解耦），由端点拿 final 事件后用 fresh session 写。
    """
    session_id = request.session_id or str(uuid4())
    thread_id = f"{user_id}:{session_id}"
    scope = request.document_ids or None

    events: "queue.Queue[dict | object]" = queue.Queue()
    _DONE = object()   # 哨兵：worker 结束

    def _produce() -> None:
        steps_by_id: dict[str, dict] = {}   # tool_call_id -> step（start 建，result 补 status/result）
        order: list[str] = []               # 保持步骤出现顺序
        citations: list[dict] = []
        seen: set[tuple[str, str]] = set()
        final_answer = ""

        # contextvar 在本 worker 线程内 set/reset：图与全部工具都在此线程同步执行，能正确读到
        token = set_current_user_id(user_id)
        scope_token = set_document_scope(scope)
        try:
            for mode, data in get_agent_graph().stream(
                {"messages": [HumanMessage(content=request.user_query)]},
                config={"configurable": {"thread_id": thread_id}, "recursion_limit": 10},
                stream_mode=["updates", "messages"],   # updates=步骤事件；messages=逐 token
            ):
                if mode == "messages":
                    # 逐 token 流：只取 agent 节点 LLM 的内容增量（工具用直连 LLM、不经 langgraph，
                    # 故不会混入；最终答案由下方 final 事件用权威全文校正）。
                    msg, meta = data
                    text = getattr(msg, "content", "") or ""
                    if text and meta.get("langgraph_node") == "agent":
                        events.put({"type": "token", "text": text})
                    continue
                for node, payload in data.items():   # mode == "updates"
                    messages = payload.get("messages", []) if isinstance(payload, dict) else []
                    for m in messages:
                        if node == "agent":
                            tool_calls = getattr(m, "tool_calls", None) or []
                            for tc in tool_calls:
                                step_no = len(order) + 1
                                steps_by_id[tc["id"]] = {
                                    "step": step_no,
                                    "action": tc["name"],
                                    "detail": str(tc.get("args", {})),
                                    "status": "ok",
                                    "result": "",
                                }
                                order.append(tc["id"])
                                events.put({
                                    "type": "step_start",
                                    "step": step_no,
                                    "action": tc["name"],
                                    "detail": str(tc.get("args", {})),
                                })
                            if not tool_calls:
                                final_answer = m.content   # 无 tool_calls 的 AI 消息 = 最终答案
                        elif node == "tools" and isinstance(m, ToolMessage):
                            s = steps_by_id.get(m.tool_call_id)
                            status = "error" if getattr(m, "status", None) == "error" else "ok"
                            result = _result_preview(m.content)
                            if s is not None:
                                s["status"], s["result"] = status, result
                            events.put({
                                "type": "step_result",
                                "step": s["step"] if s else None,
                                "status": status,
                                "result": result,
                            })
                            if m.name == "search_documents" and m.artifact:
                                for c in m.artifact:
                                    key = (c["document_id"], c["text"])
                                    if key not in seen:
                                        seen.add(key)
                                        citations.append(c)

            events.put({
                "type": "final",
                "final_answer": final_answer,
                "citations": citations,
                "steps": [steps_by_id[i] for i in order],
                "session_id": session_id,
            })
        except Exception as e:
            # 执行期异常兜底（检索/LLM/checkpointer 失败等）：发 error 事件让前端收口，绝不裸断
            events.put({"type": "error", "message": "Agent 执行失败，请稍后重试。", "session_id": session_id})
            logger.error("agent stream failed [%s]: %s", type(e).__name__, e)
        finally:
            reset_document_scope(scope_token)
            reset_current_user_id(token)
            events.put(_DONE)

    worker = threading.Thread(target=_produce, name="agent-stream", daemon=True)
    worker.start()
    while True:
        ev = events.get()
        if ev is _DONE:
            break
        yield ev  # type: ignore[misc]
    worker.join()
