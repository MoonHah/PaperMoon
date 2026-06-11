import hashlib
import logging
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.models.document import Document
from app.repositories import document_repository
from app.workers import document_tasks

logger = logging.getLogger(__name__)


def ingest(session: Session, filename: str, suffix: str, content_bytes: bytes) -> Document:
    """文档入库编排：内容指纹去重 → 落盘 → 建记录 → 投递索引任务。

    返回最终的 Document（命中去重时为已存在记录，否则为新建记录）。
    HTTP 层只负责请求校验与响应组装，业务编排集中在此。
    """
    # 内容指纹去重：同内容已存在（成功或处理中）则幂等复用，避免重复入库污染向量库
    content_hash = hashlib.sha256(content_bytes).hexdigest()
    existing = document_repository.get_by_content_hash(session, content_hash)
    if existing is not None:
        logger.info(
            "Duplicate upload detected (content_hash=%s), reusing document %s",
            content_hash[:12],
            existing.document_id,
        )
        return existing

    document_id = str(uuid4())

    # 落盘：worker 从 storage/{document_id}{suffix} 读取
    storage_dir = Path(settings.storage_path)
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_path = storage_dir / f"{document_id}{suffix}"
    file_path.write_bytes(content_bytes)

    doc = document_repository.create(
        session=session,
        document_id=document_id,
        filename=filename,
        file_type=suffix,
        content_hash=content_hash,
    )

    # 投递 Celery 任务；队列不可用则回滚（删文件 + 删记录）并抛 503
    try:
        task = document_tasks.process_document.delay(document_id)  # type: ignore[attr-defined]
    except Exception as e:
        logger.error("Failed to dispatch task for document %s: %s", document_id, e)
        file_path.unlink(missing_ok=True)
        session.delete(doc)
        session.commit()
        raise AppError(
            error_code="TASK_QUEUE_UNAVAILABLE",
            message="Task queue unavailable, please retry later.",
            status_code=503,
        )

    doc.task_id = task.id
    session.commit()
    return doc
