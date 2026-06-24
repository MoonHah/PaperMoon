"""请求级 contextvar：把当前登录用户 id、本轮对话的文档范围绑定到执行上下文。

用于 Agent 工具（@tool 由 LangGraph ToolNode 以"仅 LLM 入参"调用，拿不到 user/scope）——
graph_agent.run 进入时 set、退出时 reset，工具内 get_*() 读取：
  - current_user_id：按用户隔离（检索/列表/归属校验）。
  - current_document_scope：用户勾选的文档范围（None=不限定，全部已就绪文档）。
仿照 app/core/logging.py 的 request_id 模式。
"""

from contextvars import ContextVar, Token

_current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)
_current_document_scope: ContextVar[list[str] | None] = ContextVar(
    "current_document_scope", default=None
)


def set_current_user_id(user_id: str | None) -> Token:
    return _current_user_id.set(user_id)


def get_current_user_id() -> str | None:
    return _current_user_id.get()


def reset_current_user_id(token: Token) -> None:
    _current_user_id.reset(token)


def set_document_scope(document_ids: list[str] | None) -> Token:
    return _current_document_scope.set(document_ids)


def get_document_scope() -> list[str] | None:
    return _current_document_scope.get()


def reset_document_scope(token: Token) -> None:
    _current_document_scope.reset(token)
