import logging

from celery import Celery
from celery.signals import after_setup_logger, worker_process_init, worker_ready

from app.core.config import settings

_log = logging.getLogger(__name__)


celery_app = Celery(
    "papermoon",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.document_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
    # 单个文档处理的超时上限：防止超大/损坏 PDF 卡死 solo worker、阻塞整个队列。
    # soft 先触发并抛 SoftTimeLimitExceeded（可被任务捕获并置 FAILED）；hard 是兜底硬杀。
    # 值由 env 可配（默认含 Docling 首次模型下载的冷启动余量），见 config.py。
    task_soft_time_limit=settings.parse_task_soft_limit,
    task_time_limit=settings.parse_task_hard_limit,
)


def _apply_json_formatter(logger: logging.Logger) -> None:
    from app.core.logging import JsonFormatter
    for handler in logger.handlers:
        handler.setFormatter(JsonFormatter())


@after_setup_logger.connect
def configure_main_logging(logger, **_):
    # 主进程日志（启动信息、连接 Redis 等）
    _apply_json_formatter(logger)


@worker_process_init.connect
def init_worker_logging(**_):
    # worker 子进程日志（任务执行日志）
    from app.core.logging import setup_logging
    setup_logging()


@worker_ready.connect
def reconcile_on_startup(**_):
    # worker 就绪时对账一次：把被硬杀/重启遗留的「停滞非终态」文档置 FAILED，
    # 避免它们永久卡在 PARSING 等中间态。对账失败不应阻断 worker 启动，故全包 try。
    # worker_ready 在主进程只触发一次（区别于 worker_process_init 的每子进程）。
    from app.core.database import SessionLocal
    from app.services.document_reconcile import reconcile_stuck_documents

    db = SessionLocal()
    try:
        n = reconcile_stuck_documents(db, settings.stuck_document_timeout)
        if n:
            _log.info("startup reconcile: marked %d stuck document(s) FAILED", n)
    except Exception as e:
        _log.error("startup reconcile failed: %s", e)
    finally:
        db.close()
