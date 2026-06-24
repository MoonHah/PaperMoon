from collections.abc import Iterator
from typing import Annotated, TypedDict
from uuid import uuid4

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, trim_messages
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import SecretStr

from app.agent import tools as _impl    # 复用现有工具实现
from app.core.config import settings
from app.core.context import (
    reset_current_user_id,
    reset_document_scope,
    set_current_user_id,
    set_document_scope,
)

from app.agent.schemas import AgentRunRequest, AgentRunResponse, CitedChunk, IntermediateStep
from langgraph.checkpoint.memory import MemorySaver # for checkpointer

# ========================== LangGraph版 ReAct Agent =============================

class AgentState(TypedDict):
    # add_messages 是 reducer：节点 return {"messages": [x]} 时自动「追加」进历史（而非覆盖）
    messages: Annotated[list, add_messages]


# 系统提示：每次调用前临时注入（不写入 state，故不进 checkpointer 历史）。
# document_id 仅供 Agent 内部调工具用，不要回显给用户——用户看到 UUID 体验很差。
_SYSTEM_PROMPT = SystemMessage(
    content=(
        "你是 PaperMoon 的文档阅读助手。对用户作答时一律用文件名指代文档，"
        "绝不要向用户展示 document_id / UUID（它们仅供你内部调用工具使用）。"
    )
)


# ── 工具：@tool 的 docstring 即「给 LLM 的工具说明书」（= schema 的 description）──

@tool(response_format="content_and_artifact")
def search_documents(query: str) -> tuple[str, list[dict]]:
    """在文档库中检索与问题最相关的片段，回答关于文档内容的具体问题。当用户提问但没有明确要求总结/对比/做笔记时，默认使用这个。

    Args:
        query: 用于检索的查询文本。
    """
    # content_and_artifact：返回 (给 LLM 看的字符串, 结构化引用)。
    # 字符串进 ToolMessage.content（LLM 行为不变），结构化引用进 ToolMessage.artifact，
    # 供 run() 跑完回收成 citations——绕开「ToolNode 把结果压成字符串丢失结构」的问题。
    chunks = _impl.search_documents(query)
    content = "\n\n---\n\n".join(c.text for c in chunks) if chunks else "未找到相关内容。"
    artifact = [c.model_dump() for c in chunks]
    return content, artifact


@tool
def list_documents() -> str:
    """列出当前文档库中所有可用文档的文件名和 document_id。当用户用自然语言指代文档（如「那两篇」「关于 X 的论文」）、需要先确定具体是哪些文档时，先调它拿到真实 document_id，再调用 summarize_document / compare_documents。"""
    docs = _impl.list_documents()
    if not docs:
        return "文档库为空。"
    return "当前可用文档：\n" + "\n".join(
        f"- {d['filename']} (document_id: {d['document_id']})" for d in docs
    )


@tool
def summarize_document(document_id: str) -> str:
    """对单独一篇完整文档（由 document_id 指定）生成整体总结/概览。仅当只针对一篇文档、且不涉及与其他文档比较时使用；若用户要对比多篇文档，应改用 compare_documents。

    Args:
        document_id: 要总结的文档 ID（可先用 list_documents 获取真实 ID）。
    """
    return _impl.summarize_document(document_id)


@tool
def compare_documents(document_ids: list[str]) -> str:
    """对比两篇或多篇文档在内容、方法或结论上的异同。只要用户提到「对比」「比较」「差异」「异同」「不同」且涉及多篇文档就用它——即使问的是「方法上的差异」「结论的不同」也属于对比，不要误选 summarize_document。

    Args:
        document_ids: 要对比的文档 ID 列表，至少 2 个（可先用 list_documents 获取真实 ID）。
    """
    return _impl.compare_documents(document_ids)


@tool
def generate_markdown_notes(topic: str, query: str) -> str:
    """围绕某个主题、基于文档内容生成结构化的 Markdown 学习笔记。用户要求整理笔记时用。

    Args:
        topic: 学习笔记的主题。
        query: 用于检索相关内容的查询文本。
    """
    return _impl.generate_markdown_notes(topic, query)


# 汇总列表（绑定 LLM + 构建 ToolNode 都用它）——必须放在所有 @tool 定义之后
TOOLS = [
    search_documents,
    list_documents,
    summarize_document,
    compare_documents,
    generate_markdown_notes,
]

# ================= Checkpointer Factory =================
def _make_checkpointer():
    if settings.checkpoint_backend == "postgres":
        from psycopg_pool import ConnectionPool
        from langgraph.checkpoint.postgres import PostgresSaver

        # 连接池: FastAPI 线程池并发请求各借各的连接（单 Connection 非线程安全）
        pool = ConnectionPool(
            conninfo=settings.database_url,
            max_size=10,
            kwargs={"autocommit": True, "prepare_threshold": 0},  # PostgresSaver 要求的连接参数
        )
        # 注解要求 DictRow 池，但 PostgresSaver 内部建 cursor 时自带 row_factory=dict_row，运行时无碍
        checkpointer = PostgresSaver(pool)  # type: ignore[arg-type]
        checkpointer.setup()    # 幂等建表; checkpoint 表由 langgraph 自治, 不入 Alembic
        return checkpointer
    return MemorySaver()


# ================== Build ReAct Graph ===================

def build_agent_graph(llm=None, checkpointer=None):
    # LLM 构建收在 build 内（而非模块级）：import 本文件不再有创建客户端的副作用
    if llm is None:
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=SecretStr(settings.openai_api_key),
            base_url=settings.openai_base_url,
            timeout=settings.llm_timeout,
            temperature=0,
        ).bind_tools(TOOLS)   # bind_tools 把 TOOLS 的 schema 告诉模型（= 手写版传 tools=TOOL_SCHEMAS）
    
    def agent_node(state: AgentState) -> dict:
        """调 LLM 决策：返回 AIMessage（含 tool_calls 或最终答案）。闭包捕获 llm。

        历史修剪只作用于「LLM 看到的窗口」——checkpointer 里仍保留完整历史。
        长对话不修剪会撑爆上下文/token 成本；按条数裁（token_counter=len）避免引入 tokenizer。
        """
        window = trim_messages(
            state["messages"],
            strategy="last",                              # 保留最近的
            token_counter=len,                            # 以消息条数计数
            max_tokens=settings.agent_history_window,     # 此时语义 = 最大条数
            start_on="human",   # 窗口必须从 human 开头：孤儿 ToolMessage 会让 OpenAI 报协议错
            include_system=True,
            allow_partial=False,
        )
        # 临时前置系统提示（不入 state/checkpointer）：约束不回显 UUID
        return {"messages": [llm.invoke([_SYSTEM_PROMPT, *window])]}

    graph = StateGraph(AgentState)                          # 用 State 类型建图

    graph.add_node("agent", agent_node)                     # 节点①：调 LLM 决策
    # handle_tool_errors=True：工具抛异常时转成错误 ToolMessage 回填（= 手写版「失败回填让 LLM 重试」）
    graph.add_node("tools", ToolNode(TOOLS, handle_tool_errors=True))   # 节点②：执行工具

    graph.set_entry_point("agent")                          # 入口：先进 agent
    graph.add_conditional_edges("agent", tools_condition)   # 条件边：有 tool_calls→"tools"，无→END
    graph.add_edge("tools", "agent")                        # 回边：工具执行完回到 agent（这就是「循环」！）

    # None 才造默认（按配置选 memory/postgres）；传入的注入值必须被尊重——单一出口
    if checkpointer is None:
        checkpointer = _make_checkpointer()
    return graph.compile(checkpointer=checkpointer)


# 懒加载单例：首次调用才编译图（创建 LLM 客户端），消除 import 副作用
_graph = None


def get_agent_graph():
    global _graph
    if _graph is None:
        _graph = build_agent_graph()
    return _graph


# =================== Run Agent Service ====================

_RESULT_PREVIEW_LIMIT = 160


def _result_preview(content, limit: int = _RESULT_PREVIEW_LIMIT) -> str:
    """把工具结果压成单行短预览供轨迹展示（折叠空白 + 截断），不改动给 LLM 的原文。"""
    s = " ".join(str(content).split())
    return s if len(s) <= limit else s[:limit] + "…"


def run(request: AgentRunRequest, user_id: str) -> AgentRunResponse:
    """跑 LangGraph agent，返回与手写版一致的 AgentRunResponse（API 契约不因后端实现而变）。

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
    """流式跑 agent：把 graph.stream(updates) 的逐节点产出翻译成前端事件，实时展示推理轨迹。

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
    import logging
    import queue
    import threading

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
            logging.getLogger(__name__).error("agent stream failed [%s]: %s", type(e).__name__, e)
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