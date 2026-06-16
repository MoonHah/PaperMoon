"""document_reconcile 单测：停滞文档对账（按 updated_at 年龄门控置 FAILED）。

用 conftest 的 SQLite 内存库 db_session，零外部依赖。
"""

from datetime import datetime, timedelta

from app.models.document import Document, DocumentStatus
from app.repositories import document_repository
from app.services.document_reconcile import reconcile_stuck_documents


def _make_doc(db, doc_id: str, status: DocumentStatus, minutes_ago: int) -> None:
    ts = datetime.utcnow() - timedelta(minutes=minutes_ago)
    db.add(
        Document(
            document_id=doc_id,
            user_id="reconcile-test-user",
            filename="x.pdf",
            file_type=".pdf",
            status=status.value,
            created_at=ts,
            updated_at=ts,
        )
    )
    db.commit()


def test_reconcile_marks_old_stuck_failed(db_session):
    # 停滞 60 分钟的 PARSING（被硬杀遗留）→ 应置 FAILED 并写中断说明
    _make_doc(db_session, "old-stuck", DocumentStatus.PARSING, minutes_ago=60)
    n = reconcile_stuck_documents(db_session, max_age_seconds=300)
    assert n == 1
    doc = document_repository.get_by_id(db_session, "old-stuck")
    assert doc.status == DocumentStatus.FAILED.value
    assert "中断" in (doc.error_message or "")


def test_reconcile_skips_fresh_in_flight(db_session):
    # 刚起的在途任务（停滞 0 分钟 < 5 分钟阈值）绝不能被误杀
    _make_doc(db_session, "fresh", DocumentStatus.PARSING, minutes_ago=0)
    n = reconcile_stuck_documents(db_session, max_age_seconds=300)
    assert n == 0
    doc = document_repository.get_by_id(db_session, "fresh")
    assert doc.status == DocumentStatus.PARSING.value


def test_reconcile_ignores_terminal(db_session):
    # 终态（READY/FAILED）即使很老也不动
    _make_doc(db_session, "ready-old", DocumentStatus.READY, minutes_ago=60)
    _make_doc(db_session, "failed-old", DocumentStatus.FAILED, minutes_ago=60)
    n = reconcile_stuck_documents(db_session, max_age_seconds=300)
    assert n == 0
    assert document_repository.get_by_id(db_session, "ready-old").status == DocumentStatus.READY.value
