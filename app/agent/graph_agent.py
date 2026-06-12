from typing import Annotated, TypedDict
from uuid import uuid4

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import SecretStr

from app.agent import tools as _impl    # 复用现有工具实现
from app.core.config import settings

from app.agent.schemas import AgentRunRequest, AgentRunResponse, IntermediateStep
from langgraph.checkpoint.memory import MemorySaver # for checkpointer

# ========================== LangGraph版 ReAct Agent =============================

class AgentState(TypedDict):
    # add_messages 是 reducer：节点 return {"messages": [x]} 时自动「追加」进历史（而非覆盖）
    messages: Annotated[list, add_messages]


# ── 工具：@tool 的 docstring 即「给 LLM 的工具说明书」（= schema 的 description）──

@tool
def search_documents(query: str) -> str:
    """在文档库中检索与问题最相关的片段，回答关于文档内容的具体问题。当用户提问但没有明确要求总结/对比/做笔记时，默认使用这个。

    Args:
        query: 用于检索的查询文本。
    """
    chunks = _impl.search_documents(query)
    return "\n\n---\n\n".join(c.text for c in chunks) if chunks else "未找到相关内容。"


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

# ================== Build ReAct Graph ===================

def build_agent_graph(llm=None):
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
        """调 LLM 决策：基于完整历史，返回 AIMessage（含 tool_calls 或最终答案）。闭包捕获 llm。"""
        return {"messages": [llm.invoke(state["messages"])]}

    graph = StateGraph(AgentState)                          # 用 State 类型建图

    graph.add_node("agent", agent_node)                     # 节点①：调 LLM 决策
    # handle_tool_errors=True：工具抛异常时转成错误 ToolMessage 回填（= 手写版「失败回填让 LLM 重试」）
    graph.add_node("tools", ToolNode(TOOLS, handle_tool_errors=True))   # 节点②：执行工具

    graph.set_entry_point("agent")                          # 入口：先进 agent
    graph.add_conditional_edges("agent", tools_condition)   # 条件边：有 tool_calls→"tools"，无→END
    graph.add_edge("tools", "agent")                        # 回边：工具执行完回到 agent（这就是「循环」！）

    return graph.compile(checkpointer=MemorySaver())                                  # 编译成可调用的 app


# 懒加载单例：首次调用才编译图（创建 LLM 客户端），消除 import 副作用
_graph = None


def get_agent_graph():
    global _graph
    if _graph is None:
        _graph = build_agent_graph()
    return _graph


# =================== Run Agent Service ====================

def run(request: AgentRunRequest) -> AgentRunResponse:
    """跑 LangGraph agent，返回与手写版一致的 AgentRunResponse（API 契约不因后端实现而变）。"""
    session_id = request.session_id or str(uuid4())
    try:
        # invoke 从入口跑到 END，自动驱动 agent↔tools 循环，返回跑完的完整 state
        result = get_agent_graph().invoke(
            {"messages": [HumanMessage(content=request.user_query)]},
            config={
                "configurable": {"thread_id": session_id},  # 绑定会话
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

    return AgentRunResponse(
        final_answer=messages[-1].content,
        selected_tool="(final)",
        intermediate_steps=steps,
        # 局限：ToolNode 把工具结果压成字符串，citations 的结构化信息无法回收——框架封装的代价
        citations=[],
        session_id=session_id
    )