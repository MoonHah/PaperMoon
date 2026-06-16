from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class DocumentUploadResponse(BaseModel):
    document_id: str = Field(..., description="文章唯一标识, 用于追踪")
    filename: str = Field(description="原始文件名")
    task_id: str = Field(..., description="任务ID, 用于客户端追踪")
    status: str = Field(description="入库状态")

class DocumentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str = Field(...)
    task_id: str | None = Field(default=None)
    status: str = Field(...)
    chunk_count: int | None = Field(default=None)
    error_message: str | None = Field(default=None)

class DocumentContentResponse(BaseModel):
    document_id: str = Field(...)
    filename: str = Field(...)
    content: str = Field(description="解析后的文档正文（Markdown）")

class DocumentNotesResponse(BaseModel):
    document_id: str = Field(...)
    filename: str = Field(...)
    notes: str = Field(description="基于该文档全文生成的 Markdown 学习笔记")

class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str = Field(...)
    filename: str = Field(...)
    file_type: str = Field(...)
    status: str = Field(...)
    chunk_count: int | None = Field(default=None)
    error_message: str | None = Field(default=None)
    created_at: datetime = Field(...)
    updated_at: datetime = Field(...)
