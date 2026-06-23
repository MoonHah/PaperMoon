import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import get_current_user
from app.models.document import Document
from app.models.user import User
from app.repositories import document_repository
from app.schemas.document import (
    DocumentChunk,
    DocumentChunksResponse,
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


@router.get("/{document_id}/file")
def get_document_file(doc: Document = Depends(get_owned_document)):
    """返回上传的原件本体（阅读页内嵌渲染原始 PDF 等）。归属校验交依赖。

    前端 <iframe src> 带不了 Bearer，故前端会鉴权 fetch 成 blob 再内嵌——
    本端点只需给对字节 + media_type，Content-Disposition 不影响 blob 渲染。
    """
    path = Path(settings.storage_path) / f"{doc.document_id}{doc.file_type}"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Original file not found.")
    media = {
        ".pdf": "application/pdf",
        ".md": "text/markdown",
        ".txt": "text/plain",
    }.get(doc.file_type, "application/octet-stream")
    return FileResponse(path, media_type=media)


@router.get("/{document_id}/chunks", response_model=DocumentChunksResponse)
def get_document_chunks(
    document_id: str,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 分块检查：返回与 worker 同款规则确定性重切的分块（归属 + READY 校验在 service）。
    filename, chunks = document_service.get_chunks(session, user.id, document_id)
    return DocumentChunksResponse(
        document_id=document_id,
        filename=filename,
        chunk_count=len(chunks),
        chunks=[
            DocumentChunk(index=i, text=c, char_count=len(c)) for i, c in enumerate(chunks)
        ],
    )


@router.post("/{document_id}/notes", response_model=DocumentNotesResponse)
def generate_document_notes(
    document_id: str,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 确定性地为单篇文档生成笔记（按 document_id 锁定，喂截断后的正文）——不走 Agent，避免指代歧义。
    try:
        filename, notes = document_service.generate_notes(session, user.id, document_id)
    except AppError:
        raise  # 业务错误（404 未找到 / 409 未就绪 / 内容缺失）交全局处理器渲染
    except Exception as e:
        # LLM 超时/失败等：兜成友好 503，避免裸 500（Internal Server Error）
        logger.error("notes generation failed [%s]: %s", type(e).__name__, e)
        raise HTTPException(status_code=503, detail="笔记生成暂时失败，请稍后重试。")
    return DocumentNotesResponse(
        document_id=document_id, filename=filename, notes=notes
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(doc: Document = Depends(get_owned_document)):
    return doc


@router.delete("/{document_id}", status_code=204)
def delete_document(
    doc: Document = Depends(get_owned_document),
    session: Session = Depends(get_db),
):
    # get_owned_document 已做归属校验（非属主 404）；session 与依赖内同一请求会话。
    document_service.delete(session, doc)


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    request: Request,
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

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    too_large = HTTPException(
        status_code=413, detail=f"File exceeds {settings.max_file_size_mb} MB limit."
    )

    # ① Content-Length 预检：诚实客户端可在读 body 前就快速拒绝超大文件（省内存/带宽）。
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > max_bytes:
        raise too_large

    # ② 流式读 + 上限兜底：Content-Length 可能缺失/伪造，故边读边累计、超限即中止，
    #    内存封顶在 ~max_bytes，不会把超大文件整体读入再判断。
    content_bytes = b""
    while chunk := await file.read(1024 * 1024):  # 1 MB/次
        content_bytes += chunk
        if len(content_bytes) > max_bytes:
            raise too_large

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
