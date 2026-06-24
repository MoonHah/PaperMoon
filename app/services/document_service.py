import hashlib
import json
import logging
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.models.document import Document, DocumentStatus
from app.repositories import document_repository
from app.services.chunking_service import chunk_text
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
    "4. 不要使用任何 emoji、特殊符号或箭头（如 ↑ ↓ → ⬆ ⬇）；"
    "趋势或变化一律用文字表达（如「上升」「下降」「基本持平」）。\n"
    "5. 若使用 Markdown 表格，每个单元格都要填写具体文字内容，"
    "不要留空、也不要只用符号占位。\n"
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
    # 原件 + 解析正文 + 笔记正文/状态：一并清理，避免删文档后留孤儿文件。
    for name in (
        f"{document_id}{file_type}",
        f"{document_id}.content.md",
        f"{document_id}.notes.md",
        f"{document_id}.notes.json",
    ):
        try:
            (storage_dir / name).unlink(missing_ok=True)
        except Exception as e:
            logger.warning("删除存储文件失败 %s: %s", name, e)


def truncate_for_llm(content: str, limit: int | None = None) -> str:
    """把单次喂给 LLM 的正文截断到字符预算，避免大文档全文塞进单次调用导致超时。

    limit 默认取 settings.notes_max_chars——笔记/总结/对比共用同一预算（设 0 表示不截断）。
    超长文档因此只覆盖前段，是可接受的廉价档取舍（完整覆盖需 map-reduce）。
    """
    if limit is None:
        limit = settings.notes_max_chars
    if limit and len(content) > limit:
        logger.info("LLM 正文截断 %d→%d 字符 (limit=%d)", len(content), limit, limit)
        return content[:limit]
    return content


def get_chunks(session: Session, user_id: str, document_id: str) -> tuple[str, list[str]]:
    """返回 (filename, 分块列表)，供分块检查页使用。

    用与 worker 完全相同的 chunk_text + 同一份解析正文确定性重切——
    即「实际入库的切分」，无需查 Qdrant（向量层只存向量，不便回读原文）。
    归属/READY 校验复用 get_content（非属主 404 / 未就绪 409）。
    """
    filename, content = get_content(session, user_id, document_id)
    chunks = chunk_text(content, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)
    return filename, chunks


# ── 笔记异步生成（OpenAI 国内慢，单次可达 86-150s → 不能同步长握 HTTP）─────────
# 状态机用文件持久化（免 DB 迁移，与 content.md 落盘一致）：
#   {id}.notes.json = {"status": NOT_GENERATED|PENDING|READY|FAILED, "error": ...}
#   {id}.notes.md   = READY 时的笔记正文
NOTES_NOT_GENERATED = "NOT_GENERATED"
NOTES_PENDING = "PENDING"
NOTES_READY = "READY"
NOTES_FAILED = "FAILED"


def _notes_status_file(document_id: str) -> Path:
    return Path(settings.storage_path) / f"{document_id}.notes.json"


def _notes_md_file(document_id: str) -> Path:
    return Path(settings.storage_path) / f"{document_id}.notes.md"


def _write_notes_status(document_id: str, status: str, error: str | None = None) -> None:
    _notes_status_file(document_id).write_text(
        json.dumps({"status": status, "error": error}, ensure_ascii=False), encoding="utf-8"
    )


def request_notes(session: Session, user_id: str, document_id: str) -> str:
    """校验归属 + READY，写 PENDING 状态并投递异步任务。返回 filename。"""
    doc = document_repository.get_owned(session, user_id, document_id)
    if doc is None:
        raise AppError(error_code="NOT_FOUND", message="Document not found.", status_code=404)
    if doc.status != DocumentStatus.READY.value:
        raise AppError(
            error_code="DOCUMENT_NOT_READY", message="Document is not ready yet.", status_code=409
        )
    _write_notes_status(document_id, NOTES_PENDING)
    document_tasks.generate_notes.delay(document_id, user_id)  # type: ignore[attr-defined]
    return doc.filename


def read_notes(
    session: Session, user_id: str, document_id: str
) -> tuple[str, str, str | None, str | None]:
    """返回 (filename, status, notes|None, error|None)。归属校验（非属主 404）。"""
    doc = document_repository.get_owned(session, user_id, document_id)
    if doc is None:
        raise AppError(error_code="NOT_FOUND", message="Document not found.", status_code=404)

    status_file = _notes_status_file(document_id)
    if not status_file.exists():
        return doc.filename, NOTES_NOT_GENERATED, None, None
    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
    except Exception:
        return doc.filename, NOTES_NOT_GENERATED, None, None

    status = data.get("status", NOTES_NOT_GENERATED)
    if status == NOTES_READY:
        md = _notes_md_file(document_id)
        if md.exists():
            return doc.filename, NOTES_READY, md.read_text(encoding="utf-8"), None
        return doc.filename, NOTES_NOT_GENERATED, None, None  # 状态 READY 但文件丢了
    return doc.filename, status, None, data.get("error")


def run_notes_generation(session: Session, user_id: str, document_id: str) -> None:
    """Celery 任务体：生成笔记落盘 + 写状态。任何异常 → FAILED（不抛出，任务正常结束）。"""
    try:
        _, content = get_content(session, user_id, document_id)
        notes = get_llm_service(settings).chat(
            _NOTES_PROMPT, context_chunks=[truncate_for_llm(content)]
        )
        _notes_md_file(document_id).write_text(notes, encoding="utf-8")
        _write_notes_status(document_id, NOTES_READY)
    except Exception as e:
        logger.error("notes generation failed [%s] for %s: %s", type(e).__name__, document_id, e)
        _write_notes_status(document_id, NOTES_FAILED, error="笔记生成失败，请稍后重试。")
