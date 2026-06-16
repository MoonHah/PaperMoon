"""请求级 contextvar：把当前登录用户 id 绑定到执行上下文。

用于 Agent 工具（@tool 由 LangGraph ToolNode 以"仅 LLM 入参"调用，拿不到 user）——
graph_agent.run 进入时 set、退出时 reset，工具内 get_current_user_id() 读取以做按用户隔离。
仿照 app/core/logging.py 的 request_id 模式。
"""

from contextvars import ContextVar, Token

_current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)


def set_current_user_id(user_id: str | None) -> Token:
    return _current_user_id.set(user_id)


def get_current_user_id() -> str | None:
    return _current_user_id.get()


def reset_current_user_id(token: Token) -> None:
    _current_user_id.reset(token)
