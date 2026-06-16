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
from app.core.context import reset_current_user_id, set_current_user_id

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

def run(request: AgentRunRequest, user_id: str) -> AgentRunResponse:
    """跑 LangGraph agent，返回与手写版一致的 AgentRunResponse（API 契约不因后端实现而变）。

    user_id：经 contextvar 注入，供工具按用户隔离检索/列表/归属校验；
    thread_id 也用 user 命名空间，防跨用户猜 session。
    """
    session_id = request.session_id or str(uuid4())
    thread_id = f"{user_id}:{session_id}"   # 会话按用户隔离
    token = set_current_user_id(user_id)
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
        reset_current_user_id(token)

    # 完整历史：Human → AI(tool_calls) → Tool → … → AI(最终答案)
    messages = result["messages"]
    last_human = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
    current_turn = messages[last_human:]

    # 把历史里的 tool_calls 翻译成 IntermediateStep（与手写版的轨迹格式对齐）
    steps = [
        IntermediateStep(step=i + 1, action=tc["name"], detail=str(tc.get("args", {})), status="ok")
        for i, tc in enumerate(
            tc for m in current_turn for tc in (getattr(m, "tool_calls", None) or [])
        )
    ]

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