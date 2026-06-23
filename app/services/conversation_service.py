from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agent.schemas import AgentRunResponse
from app.core.errors import AppError
from app.models.conversation import Conversation, Message
from app.repositories import conversation_repository


def _title(user_query: str) -> str:
    return user_query.strip()[:40] or "新对话"


def _extra(response: AgentRunResponse) -> dict:
    # assistant 行存 citations/steps，供历史完整回放（与实时一致）。
    return {
        "citations": [c.model_dump() for c in response.citations],
        "steps": [s.model_dump() for s in response.intermediate_steps],
    }


def record_turn(
    session: Session,
    user_id: str,
    conversation_id: str,
    user_query: str,
    response: AgentRunResponse,
) -> None:
    """agent run 成功后落库：会话不存在则建（标题取首条问题），存 user + assistant 两条消息。"""
    conv = conversation_repository.get_owned(session, user_id, conversation_id)
    if conv is None:
        conv = conversation_repository.create(session, conversation_id, user_id, _title(user_query))
    conversation_repository.add_message(session, conversation_id, "user", user_query)
    conversation_repository.add_message(
        session, conversation_id, "assistant", response.final_answer, extra=_extra(response)
    )
    conv.updated_at = datetime.now(timezone.utc)  # 续聊置顶
    session.commit()


def list_conversations(session: Session, user_id: str) -> list[Conversation]:
    return conversation_repository.list_by_user(session, user_id)


def get_conversation(
    session: Session, user_id: str, conversation_id: str
) -> tuple[Conversation, list[Message]]:
    conv = conversation_repository.get_owned(session, user_id, conversation_id)
    if conv is None:
        raise AppError(error_code="NOT_FOUND", message="Conversation not found.", status_code=404)
    return conv, conversation_repository.list_messages(session, conversation_id)


def delete_conversation(session: Session, user_id: str, conversation_id: str) -> None:
    conv = conversation_repository.get_owned(session, user_id, conversation_id)
    if conv is None:
        raise AppError(error_code="NOT_FOUND", message="Conversation not found.", status_code=404)
    conversation_repository.delete(session, conv)
    session.commit()
