from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: str
    title: str
    updated_at: datetime


class MessageOut(BaseModel):
    role: str = Field(description="user | assistant")
    content: str
    extra: dict | None = Field(default=None, description="assistant 行的 citations/steps")


class ConversationDetail(BaseModel):
    conversation_id: str
    title: str
    messages: list[MessageOut]
