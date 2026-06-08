from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.repositories import document_repository
from app.schemas.document import DocumentResponse, DocumentStatusResponse, DocumentUploadResponse
from app.workers import document_tasks

router = APIRouter()

ALLOWED_EXTENSIONS = {".txt", ".md"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.get("/", response_model=list[DocumentResponse])
def list_documents(session: Session = Depends(get_db)):
    return document_repository.get_all(session)


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
def get_document_status(document_id: str, session: Session = Depends(get_db)):
    doc = document_repository.get_by_id(session, document_id=document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, session: Session = Depends(get_db)):
    doc = document_repository.get_by_id(session, document_id=document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: .txt, .md",
        )

    content_bytes = await file.read()

    if len(content_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit.")

    try:
        content_bytes.decode("utf-8")   # 只验证编码，文件以字节写入磁盘
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded.")

    document_id = str(uuid4())

    # 保存文件到 storage/{document_id}{suffix}，worker 从这里读取
    storage_dir = Path(settings.storage_path)
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = storage_dir / f"{document_id}{suffix}"
    file_path.write_bytes(content_bytes)

    # 创建 DB 记录（status=UPLOADED）
    doc = document_repository.create(
        session=session,
        document_id=document_id,
        filename=file.filename,
        file_type=suffix,
    )

    # 投递 Celery 任务，task.id 是 Celery 分配的 UUID
    task = document_tasks.process_document.delay(document_id)  # type: ignore[attr-defined]

    # 把 task_id 存回 DB，方便后续追踪
    doc.task_id = task.id
    session.commit()

    return DocumentUploadResponse(
        document_id=document_id,
        task_id=task.id,
        filename=file.filename,
        status="UPLOADED",
    )
