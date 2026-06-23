from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.conversation import ConversationDetail, ConversationSummary, MessageOut
from app.services import conversation_service

router = APIRouter()


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(
    session: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return conversation_service.list_conversations(session, user.id)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conv, messages = conversation_service.get_conversation(session, user.id, conversation_id)
    return ConversationDetail(
        conversation_id=conv.conversation_id,
        title=conv.title,
        messages=[MessageOut(role=m.role, content=m.content, extra=m.extra) for m in messages],
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: str,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    conversation_service.delete_conversation(session, user.id, conversation_id)
