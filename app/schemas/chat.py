from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., description="用户问题")
    top_k: int = Field(3, ge=1, le=10, description="检索几个chunk")


class ChatResponse(BaseModel):
    answer: str = Field(description="LLM回复")
    retrieved_chunks: list[str] = Field(description="检索到的原文片段列表")
    error: str | None = Field(None, description="错误类型，正常时为 null")