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
    action: str            # 工具名
    detail: str            # 入参（LLM 决定调用时传的 args）
    status: str            # "ok" | "error"——如实反映该工具是否执行成功
    result: str = ""       # 工具产出的单行短预览（成功=结果摘要 / 失败=错误信息）


class AgentRunResponse(BaseModel):
    final_answer: str
    selected_tool: str
    intermediate_steps: list[IntermediateStep]
    citations: list[CitedChunk] = Field(default=[])
    error: str | None = None
    session_id: str | None = Field(default=None)
