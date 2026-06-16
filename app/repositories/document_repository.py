from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus

# 终态：处理已结束，不再变化。
_TERMINAL_STATUSES = (DocumentStatus.READY.value, DocumentStatus.FAILED.value)


def create(
    session: Session,
    document_id: str,
    user_id: str,
    filename: str,
    file_type: str,
    content_hash: str | None = None,
) -> Document:
    doc = Document(
        document_id=document_id,
        user_id=user_id,
        filename=filename,
        file_type=file_type,
        content_hash=content_hash,
        status=DocumentStatus.UPLOADED.value,
    )
    session.add(doc)
    session.flush()
    return doc


def get_by_id(session: Session, document_id: str) -> Document | None:
    stmt = select(Document).where(Document.document_id == document_id)   # SELECT * FROM documents WHERE ...
    result = session.execute(stmt).scalar_one_or_none()
    return result


def get_owned(session: Session, user_id: str, document_id: str) -> Document | None:
    """按归属取文档：仅当文档属于该用户才返回，否则 None（多租户访问控制）。"""
    stmt = select(Document).where(
        Document.document_id == document_id,
        Document.user_id == user_id,
    )
    return session.execute(stmt).scalar_one_or_none()


def get_by_content_hash(
    session: Session, content_hash: str, user_id: str
) -> Document | None:
    """按内容指纹查找该用户已存在的文档（用于上传去重，按用户隔离）。

    只匹配未失败的记录：之前 FAILED 的同内容文件应允许重新上传重试。
    """
    stmt = select(Document).where(
        Document.content_hash == content_hash,
        Document.user_id == user_id,
        Document.status != DocumentStatus.FAILED.value,
    )
    return session.execute(stmt).scalars().first()


def get_all_by_user(session: Session, user_id: str) -> list[Document]:
    stmt = select(Document).where(Document.user_id == user_id)
    return list(session.execute(stmt).scalars().all())


def get_stuck(session: Session, before: datetime) -> list[Document]:
    """查找停滞文档：非终态（仍在处理中）且 updated_at 早于 before。

    用于对账/清理被硬杀（worker 重启 / OOM）遗留、永远落不到终态的记录。
    """
    stmt = select(Document).where(
        Document.status.not_in(_TERMINAL_STATUSES),
        Document.updated_at < before,
    )
    return list(session.execute(stmt).scalars().all())


def update_status(
    session: Session,
    document_id: str,
    status: DocumentStatus,
    chunk_count: int | None = None,
    error_message: str | None = None,
) -> Document | None:
    doc = get_by_id(session=session, document_id=document_id)
    if doc is None:
        return None
    doc.status = status.value
    if chunk_count is not None:
        doc.chunk_count = chunk_count
    if error_message is not None:
        doc.error_message = error_message
    session.flush()                     # 把内存对象的修改 flush 到 DB
    return doc
