import logging

import openai
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# OpenAI 瞬时错误：超时、连接失败、限流。鉴权/参数错误不在此列（重试无意义）。
OPENAI_RETRY_ON = (
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.RateLimitError,
)


def openai_retry(max_retries: int, logger: logging.Logger):
    """构造对 OpenAI 瞬时错误指数退避重试的 tenacity 装饰器。

    llm_service 与 embedding_service 共享同一套重试策略，避免重复配置，
    也消除了「embedding 跨模块导入 llm_service 私有 _RETRY_ON」的耦合。
    """
    return retry(
        retry=retry_if_exception_type(OPENAI_RETRY_ON),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(max_retries),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
