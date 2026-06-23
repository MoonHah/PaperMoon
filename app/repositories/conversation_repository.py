from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, Message


def get_owned(session: Session, user_id: str, conversation_id: str) -> Conversation | None:
    return session.execute(
        select(Conversation).where(
            Conversation.conversation_id == conversation_id,
            Conversation.user_id == user_id,
        )
    ).scalar_one_or_none()


def list_by_user(session: Session, user_id: str) -> list[Conversation]:
    return list(
        session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        ).scalars()
    )


def create(session: Session, conversation_id: str, user_id: str, title: str) -> Conversation:
    conv = Conversation(conversation_id=conversation_id, user_id=user_id, title=title)
    session.add(conv)
    session.flush()
    return conv


def add_message(
    session: Session, conversation_id: str, role: str, content: str, extra: dict | None = None
) -> Message:
    msg = Message(
        id=str(uuid4()), conversation_id=conversation_id, role=role, content=content, extra=extra
    )
    session.add(msg)
    session.flush()
    return msg


def list_messages(session: Session, conversation_id: str) -> list[Message]:
    return list(
        session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at, Message.id)
        ).scalars()
    )


def delete(session: Session, conv: Conversation) -> None:
    # 显式删消息（不依赖 DB 级联，SQLite 默认不开外键级联）。
    session.query(Message).filter(Message.conversation_id == conv.conversation_id).delete()
    session.delete(conv)
