"""工具层（app/agent/tools）直接单测：按用户隔离 + 范围限定 + READY 过滤 + 指导性错误。

依赖 conftest 的 _bind_sessionlocal_to_test_engine：工具内 database.SessionLocal() 走测试内存库。
工具读 contextvar 拿 user/scope，故每个用例显式 set，autouse fixture 复位防泄漏到别的测试。
"""

import pytest
from sqlalchemy.orm import Session

from app.agent import tools
from app.core.context import set_current_user_id, set_document_scope
from app.models.document import Document, DocumentStatus


@pytest.fixture(autouse=True)
def _clear_ctx():
    # 复位到默认 None，避免 contextvar 跨用例泄漏（pytest 同线程顺序跑）
    yield
    set_current_user_id(None)
    set_document_scope(None)


def _add_doc(db: Session, doc_id: str, user_id: str, status: DocumentStatus = DocumentStatus.READY):
    db.add(
        Document(
            document_id=doc_id,
            user_id=user_id,
            filename=f"{doc_id}.pdf",
            file_type=".pdf",
            status=status.value,
        )
    )
    db.commit()


# ── list_documents：隔离 + READY 过滤 + 范围限定 ──

def test_list_documents_none_user_returns_empty():
    set_current_user_id(None)
    assert tools.list_documents() == []


def test_list_documents_only_ready_and_owned(db_session: Session):
    _add_doc(db_session, "d-ready", "u1", DocumentStatus.READY)
    _add_doc(db_session, "d-parsing", "u1", DocumentStatus.PARSING)  # 非 READY → 不出
    _add_doc(db_session, "d-other", "u2", DocumentStatus.READY)      # 别人的 → 不出
    set_current_user_id("u1")

    ids = {d["document_id"] for d in tools.list_documents()}
    assert ids == {"d-ready"}


def test_list_documents_scope_filters(db_session: Session):
    _add_doc(db_session, "d1", "u1")
    _add_doc(db_session, "d2", "u1")
    set_current_user_id("u1")
    set_document_scope(["d1"])

    ids = {d["document_id"] for d in tools.list_documents()}
    assert ids == {"d1"}


# ── summarize / compare：指导性错误（3a）+ 入参护栏（3b）──

def test_summarize_unknown_document_gives_guidance(db_session: Session):
    set_current_user_id("u1")
    with pytest.raises(ValueError) as ei:
        tools.summarize_document("ghost")
    assert "list_documents" in str(ei.value)


def test_compare_requires_two_distinct_documents():
    set_current_user_id("u1")
    with pytest.raises(ValueError) as ei:
        tools.compare_documents(["d1", "d1"])  # 去重后只剩 1 篇
    assert "list_documents" in str(ei.value)


def test_compare_unknown_document_gives_guidance():
    set_current_user_id("u1")
    with pytest.raises(ValueError) as ei:
        tools.compare_documents(["ghost1", "ghost2"])
    assert "list_documents" in str(ei.value)
