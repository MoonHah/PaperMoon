import hashlib
import logging
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.models.document import Document, DocumentStatus
from app.repositories import document_repository
from app.services.document_parser import parse_document
from app.services.llm_service import get_llm_service
from app.services.vector_store import get_vector_store
from app.workers import document_tasks

logger = logging.getLogger(__name__)

_NOTES_PROMPT = (
    "请基于以上文档内容，生成一份结构化的 Markdown 学习笔记。\n"
    "要求：\n"
    "1. 用 ## 分隔主要章节\n"
    "2. 包含核心概念解释、关键要点和示例\n"
    "3. 结尾附一个「总结」章节\n"
    "只使用文档中提供的内容，不要补充额外信息。"
)


def ingest(
    session: Session, user_id: str, filename: str, suffix: str, content_bytes: bytes
) -> Document:
    """文档入库编排：内容指纹去重 → 落盘 → 建记录 → 投递索引任务。

    返回最终的 Document（命中去重时为已存在记录，否则为新建记录）。
    去重按用户隔离；HTTP 层只负责请求校验与响应组装，业务编排集中在此。
    """
    # 内容指纹去重：同用户、同内容已存在（成功或处理中）则幂等复用
    content_hash = hashlib.sha256(content_bytes).hexdigest()
    existing = document_repository.get_by_content_hash(session, content_hash, user_id)
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
        user_id=user_id,
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


def _read_text(document_id: str, file_type: str) -> str:
    """取解析后的正文：优先读索引时持久化的 {id}.content.md；
    旧文档（无该文件）则用 parse_document 重解析原文件并懒回填，下次直接读。
    原文件也缺失时抛 FileNotFoundError。
    """
    storage_dir = Path(settings.storage_path)
    parsed_path = storage_dir / f"{document_id}.content.md"
    if parsed_path.exists():
        return parsed_path.read_text(encoding="utf-8")

    original = storage_dir / f"{document_id}{file_type}"
    if not original.exists():
        raise FileNotFoundError(str(original))
    content = parse_document(original)
    try:
        parsed_path.write_text(content, encoding="utf-8")
    except Exception as e:
        logger.warning("lazy backfill parsed content failed for %s: %s", document_id, e)
    return content


def load_text(session: Session, user_id: str | None, document_id: str) -> str:
    """按 document_id 取正文（供 Agent 工具复用，按用户归属校验）。
    找不到/非属主/无内容时抛 ValueError——与工具层错误约定一致（会被捕获成工具错误回填）。
    """
    doc = document_repository.get_owned(session, user_id, document_id) if user_id else None
    if doc is None:
        raise ValueError(f"Document {document_id} not found.")
    try:
        return _read_text(document_id, doc.file_type)
    except FileNotFoundError:
        raise ValueError(f"Document {document_id} content unavailable.")


def get_content(session: Session, user_id: str, document_id: str) -> tuple[str, str]:
    """返回 (filename, 解析后的正文)。供阅读接口使用（归属 + READY 校验 + AppError）。"""
    doc = document_repository.get_owned(session, user_id, document_id)
    if doc is None:
        raise AppError(error_code="NOT_FOUND", message="Document not found.", status_code=404)
    if doc.status != DocumentStatus.READY.value:
        raise AppError(
            error_code="DOCUMENT_NOT_READY",
            message="Document is not ready yet.",
            status_code=409,
        )
    try:
        return doc.filename, _read_text(document_id, doc.file_type)
    except FileNotFoundError:
        raise AppError(
            error_code="CONTENT_UNAVAILABLE",
            message="Document content is unavailable.",
            status_code=404,
        )


def delete(session: Session, doc: Document) -> None:
    """删除文档：先删 DB 行（真相源）并提交，再尽力清理向量与存储文件。

    顺序刻意：DB 先删，外部副作用（Qdrant/文件）best-effort 且失败不回滚 DB——
    宁可留下可后续清理的孤儿向量/文件，也不要"DB 仍有记录但内容已损"的坏状态。
    doc 由路由经 get_owned_document 依赖加载（已做归属校验）。
    """
    document_id = doc.document_id
    file_type = doc.file_type

    session.delete(doc)
    session.commit()

    try:
        get_vector_store(settings).delete_by_document_id(document_id)
    except Exception as e:
        logger.warning("删除向量失败 %s: %s", document_id, e)

    storage_dir = Path(settings.storage_path)
    for name in (f"{document_id}{file_type}", f"{document_id}.content.md"):
        try:
            (storage_dir / name).unlink(missing_ok=True)
        except Exception as e:
            logger.warning("删除存储文件失败 %s: %s", name, e)


def _truncate_for_notes(content: str) -> str:
    """把正文截断到 settings.notes_max_chars，避免大文档全文塞进单次 LLM 调用导致超时。
    设 0 表示不截断。超长文档因此只覆盖前段——可接受的廉价档取舍（完整覆盖需 map-reduce）。
    """
    limit = settings.notes_max_chars
    if limit and len(content) > limit:
        logger.info("notes 正文截断 %d→%d 字符 (notes_max_chars)", len(content), limit)
        return content[:limit]
    return content


def generate_notes(session: Session, user_id: str, document_id: str) -> tuple[str, str]:
    """为单篇文档生成 Markdown 学习笔记，返回 (filename, notes)。

    确定性操作：按 document_id 精确锁定、喂正文给 LLM（区别于 Agent 通用对话——
    后者忽略 document_ids，且 generate_markdown_notes 工具只按 query 全库检索）。
    正文按 notes_max_chars 截断，保证单次调用快而稳（见 _truncate_for_notes）。
    """
    filename, content = get_content(session, user_id, document_id)
    llm = get_llm_service(settings)
    notes = llm.chat(_NOTES_PROMPT, context_chunks=[_truncate_for_notes(content)])
    return filename, notes
