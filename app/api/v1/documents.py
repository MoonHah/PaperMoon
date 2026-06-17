import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.document import Document
from app.models.user import User
from app.repositories import document_repository
from app.schemas.document import (
    DocumentContentResponse,
    DocumentNotesResponse,
    DocumentResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from app.services import document_service

router = APIRouter()

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}


def get_owned_document(
    document_id: str,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Document:
    """依赖：取当前用户拥有的文档，否则 404。收敛归属校验，避免各端点重复。"""
    doc = document_repository.get_owned(session, user.id, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.get("/", response_model=list[DocumentResponse])
def list_documents(
    session: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return document_repository.get_all_by_user(session, user.id)


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
def get_document_status(doc: Document = Depends(get_owned_document)):
    return doc


@router.get("/{document_id}/content", response_model=DocumentContentResponse)
def get_document_content(
    document_id: str,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 取正文：归属校验 + 读持久化解析文件（旧文档懒回填重解析）。
    filename, content = document_service.get_content(session, user.id, document_id)
    return DocumentContentResponse(
        document_id=document_id, filename=filename, content=content
    )


@router.post("/{document_id}/notes", response_model=DocumentNotesResponse)
def generate_document_notes(
    document_id: str,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 确定性地为单篇文档生成笔记（按 document_id 锁定，喂全文）——不走 Agent，避免指代歧义。
    filename, notes = document_service.generate_notes(session, user.id, document_id)
    return DocumentNotesResponse(
        document_id=document_id, filename=filename, notes=notes
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(doc: Document = Depends(get_owned_document)):
    return doc


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # —— HTTP 层职责：请求合法性校验 ——
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: .txt, .md, .pdf",
        )

    content_bytes = await file.read()

    if len(content_bytes) > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit.")

    if suffix != ".pdf":
        try:
            content_bytes.decode("utf-8")   # 只验证编码，文件以字节写入磁盘
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File must be UTF-8 encoded.")

    # —— 业务编排下沉到 service 层 ——
    doc = document_service.ingest(session, user.id, file.filename, suffix, content_bytes)

    return DocumentUploadResponse(
        document_id=doc.document_id,
        task_id=doc.task_id or "",
        filename=doc.filename,
        status=doc.status,
    )
