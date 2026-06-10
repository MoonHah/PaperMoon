from sqlalchemy import select

from sqlalchemy.orm import Session
from app.models.document import Document, DocumentStatus


def create(session: Session, document_id: str, filename: str, file_type: str) -> Document:
    doc = Document(
        document_id = document_id,
        filename=filename,
        file_type=file_type,
        status=DocumentStatus.UPLOADED.value)
    
    session.add(doc)
    session.flush()
    return doc


def get_by_id(session: Session, document_id: str) -> Document | None:
    stmt = select(Document).where(Document.document_id == document_id)   # 构造: SELECT * FROM documents
    result = session.execute(stmt).scalar_one_or_none()                  # 执行 + 获取
    return result


def get_all(session: Session) -> list[Document]:
    stmt = select(Document)
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
    session.flush()                     # 没有 flush() 的话, 修改只存在于 session 的内存对象中, 不会发给数据库
    return doc



                        