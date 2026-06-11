import logging

from celery import Celery
from celery.signals import after_setup_logger, worker_process_init

from app.core.config import settings


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
    task_soft_time_limit=120,
    task_time_limit=150,
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
