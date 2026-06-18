"""document_repository.update_status：error_message 仅 FAILED 保留，其它状态清空。"""

from app.models.document import DocumentStatus
from app.repositories import document_repository


def test_update_status_clears_error_message_on_non_failed(db_session):
    document_repository.create(
        db_session, document_id="d1", user_id="u1", filename="x.pdf", file_type=".pdf"
    )
    db_session.commit()

    # 先失败并写入错误信息
    document_repository.update_status(
        db_session, "d1", DocumentStatus.FAILED, error_message="boom"
    )
    assert document_repository.get_by_id(db_session, "d1").error_message == "boom"

    # 重处理成功 → 错误信息应被清空，不残留
    document_repository.update_status(
        db_session, "d1", DocumentStatus.READY, chunk_count=5
    )
    doc = document_repository.get_by_id(db_session, "d1")
    assert doc.status == DocumentStatus.READY.value
    assert doc.error_message is None
    assert doc.chunk_count == 5
