"""停滞文档对账：把被中断（worker 重启 / 硬杀 / OOM / 超时）遗留的非终态文档置 FAILED。

worker 的 except 分支只能在「进程还活着」时置 FAILED；被 SIGKILL（容器重建 / OOM）连 worker
一起杀掉时 except 跑不了，文档会永久卡在 PARSING 等中间态。本模块按 updated_at 年龄门控做兜底：
只处理「停滞超过阈值」的记录，绝不误杀另一个 worker 刚起的在途任务。

清理脚本（scripts/cleanup_documents.py）与 worker 启动钩子共用 find_stuck_documents。
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.repositories import document_repository

logger = logging.getLogger(__name__)

_INTERRUPTED_MESSAGE = "处理被中断（worker 重启或超时），请重新上传"


def _utc_naive_now() -> datetime:
    # documents.updated_at 是 timestamp without time zone，存的是 UTC 朴素时间；
    # 比较阈值也用 UTC 朴素时间对齐，避免 aware/naive 混用报错。
    return datetime.now(timezone.utc).replace(tzinfo=None)


def find_stuck_documents(session: Session, max_age_seconds: int) -> list[Document]:
    """查出停滞超过 max_age_seconds 的非终态文档。"""
    before = _utc_naive_now() - timedelta(seconds=max_age_seconds)
    return document_repository.get_stuck(session, before)


def reconcile_stuck_documents(session: Session, max_age_seconds: int) -> int:
    """把停滞文档置 FAILED，返回处理条数。"""
    stuck = find_stuck_documents(session, max_age_seconds)
    for doc in stuck:
        document_repository.update_status(
            session,
            doc.document_id,
            DocumentStatus.FAILED,
            error_message=_INTERRUPTED_MESSAGE,
        )
    session.commit()
    if stuck:
        logger.warning(
            "reconcile: marked %d stuck document(s) FAILED (age > %ds): %s",
            len(stuck),
            max_age_seconds,
            [d.document_id[:8] for d in stuck],
        )
    return len(stuck)
