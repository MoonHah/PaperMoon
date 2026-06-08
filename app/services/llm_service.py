import logging
from typing import Protocol

import openai
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

_RETRY_ON = (
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.RateLimitError,
)


class LLMClient(Protocol):
    def chat(self, query: str, context_chunks: list[str]) -> str: ...


class MockLLMService:
    def chat(self, query: str, context_chunks: list[str]) -> str:
        if not context_chunks:
            return "[MOCK] No relevant context found."
        context = "\n\n---\n\n".join(
            f"[Chunk {i+1}]\n{chunk}"
            for i, chunk in enumerate(context_chunks)
        )
        return f"[MOCK] Query: {query}\n\nRetrieved context:\n\n{context}"


class OpenAILLMService:
    def __init__(self, api_key: str, base_url: str, model: str, timeout: float, max_retries: int):
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries

    def chat(self, query: str, context_chunks: list[str]) -> str:
        context = "\n\n---\n\n".join(context_chunks)

        @retry(
            retry=retry_if_exception_type(_RETRY_ON),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            stop=stop_after_attempt(self._max_retries),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        def _call() -> str:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个基于文档回答问题的助手，只根据提供的上下文回答，如果上下文中没有答案请明确说明。",
                    },
                    {
                        "role": "user",
                        "content": f"上下文：\n{context}\n\n问题: {query}",
                    },
                ],
                timeout=self._timeout,
            )
            return resp.choices[0].message.content or ""

        return _call()


class ResilientLLMService:
    """Wraps a primary LLMClient with a fallback. If the primary exhausts all tenacity
    retries and raises, the fallback (MockLLMService) is used and the failure is logged."""

    def __init__(self, primary: LLMClient, fallback: LLMClient):
        self._primary = primary
        self._fallback = fallback

    def chat(self, query: str, context_chunks: list[str]) -> str:
        from app.core.logging import get_request_id

        try:
            return self._primary.chat(query, context_chunks)
        except Exception as e:
            logger.warning(
                "Primary LLM failed after retries, switching to fallback. "
                "error=%s request_id=%s",
                type(e).__name__,
                get_request_id(),
            )
            return self._fallback.chat(query, context_chunks)


def get_llm_service(settings) -> LLMClient:
    if settings.llm_mode == "mock":
        return MockLLMService()
    primary = OpenAILLMService(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.llm_model,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
    )
    return ResilientLLMService(primary=primary, fallback=MockLLMService())
