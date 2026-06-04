from pydantic import BaseModel, Field

class DocumentUploadResponse(BaseModel):
    document_id: str = Field(..., description="文章唯一标识, 用于追踪")
    filename: str = Field(description="原始文件名")
    chunk_count: int = Field(description="切分后的chunk数量")
    status: str = Field(description="入库状态")