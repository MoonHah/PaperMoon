from pydantic import BaseModel, Field


class CitedChunk(BaseModel):
    text: str
    document_id: str
    filename: str


class AgentRunRequest(BaseModel):
    user_query: str
    document_ids: list[str] = Field(default=[])
    session_id: str | None = Field(default=None)


class IntermediateStep(BaseModel):
    step: int
    action: str
    detail: str
    status: str


class AgentRunResponse(BaseModel):
    final_answer: str
    selected_tool: str
    intermediate_steps: list[IntermediateStep]
    citations: list[CitedChunk] = Field(default=[])
    error: str | None = None
    session_id: str | None = Field(default=None)
