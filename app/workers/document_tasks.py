import logging
import time
import uuid
from pathlib import Path

from app.core.database import SessionLocal
from app.core.logging import set_request_id
from app.models.document import DocumentStatus
from app.repositories import document_repository
from app.services.chunking_service import chunk_text
from app.services.embedding_service import get_embedding_service
from app.services.vector_store import get_vector_store
from app.core.config import settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="document_tasks.process_document",
    autoretry_for=(OSError, ConnectionError),   # 仅对基础设施瞬时故障重试；ValueError 等业务错误不重试
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def process_document(self, document_id: str) -> dict:
    task_id = self.request.id if self.request.id else uuid.uuid4().hex
    set_request_id(task_id[:8])
    t_start = time.perf_counter()

    def _elapsed() -> float:
        return round((time.perf_counter() - t_start) * 1000, 2)

    def _log_status(status: str, **extra) -> None:
        logger.info(
            "task.status",
            extra={"document_id": document_id, "task_id": task_id, "status": status, "elapsed_ms": _elapsed(), **extra},
        )

    db = SessionLocal()
    try:
        doc = document_repository.get_by_id(db, document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found in database.")

        document_repository.update_status(db, document_id, DocumentStatus.PARSING)
        db.commit()
        _log_status("PARSING")
        file_path = Path(settings.storage_path) / f"{document_id}{doc.file_type}"
        content = file_path.read_text(encoding="utf-8")

        document_repository.update_status(db, document_id, DocumentStatus.CHUNKING)
        db.commit()
        _log_status("CHUNKING")
        chunks = chunk_text(content, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)
        if not chunks:
            raise ValueError("Document has no extractable content.")

        document_repository.update_status(db, document_id, DocumentStatus.EMBEDDING)
        db.commit()
        _log_status("EMBEDDING")
        embedding_client = get_embedding_service(settings)
        embeddings = [embedding_client.embed(chunk) for chunk in chunks]

        document_repository.update_status(db, document_id, DocumentStatus.INDEXING)
        db.commit()
        _log_status("INDEXING")
        vector_store = get_vector_store(settings)
        vector_store.delete_by_document_id(document_id)
        vector_store.upsert(
            document_id=document_id,
            filename=doc.filename,
            chunks=chunks,
            embeddings=embeddings,
        )

        document_repository.update_status(db, document_id, DocumentStatus.READY, chunk_count=len(chunks))
        db.commit()
        _log_status("READY", chunk_count=len(chunks))
        return {"document_id": document_id, "chunk_count": len(chunks)}

    except Exception as e:
        is_last_attempt = self.request.retries >= self.max_retries
        logger.error(
            "task.failed",
            extra={
                "document_id": document_id,
                "task_id": task_id,
                "attempt": self.request.retries + 1,
                "max_attempts": self.max_retries + 1,
                "error": str(e),
                "elapsed_ms": _elapsed(),
            },
        )
        if is_last_attempt:
            try:
                document_repository.update_status(
                    db, document_id, DocumentStatus.FAILED, error_message=str(e)
                )
                db.commit()
            except Exception:
                pass
        raise

    finally:
        db.close()
