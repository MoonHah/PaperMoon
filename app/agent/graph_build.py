"""ReAct 图构建：AgentState + agent_node(LLM 决策 + 历史修剪) + checkpointer 工厂 + build_agent_graph。

与工具定义(tool_defs)、运行服务(graph_agent.run/run_stream)解耦——本模块只负责"图长什么样、怎么编译"。
"""

from typing import Annotated, TypedDict

from langchain_core.messages import trim_messages
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import SecretStr

from app.agent.tool_defs import TOOLS, _SYSTEM_PROMPT
from app.core.config import settings


class AgentState(TypedDict):
    # add_messages 是 reducer：节点 return {"messages": [x]} 时自动「追加」进历史（而非覆盖）
    messages: Annotated[list, add_messages]


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
        # 临时前置系统提示（不入 state/checkpointer）：约束来源优先级 + 不回显 UUID
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
