import logging
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
    autoretry_for=(Exception,),
    max_retries=3,
    retry_backoff=True,      # 指数退避: 第1次重试等2s, 第2次4s, 第3次8s
    retry_backoff_max=60,
    retry_jitter=True,       # 加随机抖动，防止多任务同时重试打爆下游服务
)
def process_document(self, document_id: str) -> dict:
    set_request_id(uuid.uuid4().hex[:8])
    db = SessionLocal()
    try:
        doc = document_repository.get_by_id(db, document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found in database.")

        document_repository.update_status(db, document_id, DocumentStatus.PARSING)
        db.commit()
        logger.info("[%s] PARSING", document_id)
        file_path = Path(settings.storage_path) / f"{document_id}{doc.file_type}"
        content = file_path.read_text(encoding="utf-8")

        document_repository.update_status(db, document_id, DocumentStatus.CHUNKING)
        db.commit()
        logger.info("[%s] CHUNKING", document_id)
        chunks = chunk_text(content, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)
        if not chunks:
            raise ValueError("Document has no extractable content.")

        document_repository.update_status(db, document_id, DocumentStatus.EMBEDDING)
        db.commit()
        logger.info("[%s] EMBEDDING", document_id)
        embedding_client = get_embedding_service(settings)
        embeddings = [embedding_client.embed(chunk) for chunk in chunks]

        document_repository.update_status(db, document_id, DocumentStatus.INDEXING)
        db.commit()
        logger.info("[%s] INDEXING", document_id)
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
        logger.info("[%s] READY - %d chunks indexed", document_id, len(chunks))
        return {"document_id": document_id, "chunk_count": len(chunks)}

    except Exception as e:
        is_last_attempt = self.request.retries >= self.max_retries
        logger.error(
            "[%s] FAILED (attempt %d/%d): %s",
            document_id,
            self.request.retries + 1,
            self.max_retries + 1,
            e,
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
