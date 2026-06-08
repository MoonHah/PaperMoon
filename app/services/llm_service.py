import json
import logging
from collections.abc import Iterator
from typing import Protocol

import httpx
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

_RAG_SYSTEM_PROMPT = (
    "你是一个基于文档回答问题的助手，只根据提供的上下文回答，如果上下文中没有答案请明确说明。"
)


class LLMClient(Protocol):
    def chat(self, query: str, context_chunks: list[str]) -> str: ...
    def stream_chat(self, query: str, context_chunks: list[str]) -> Iterator[str]: ...


class MockLLMService:
    def chat(self, query: str, context_chunks: list[str]) -> str:
        if not context_chunks:
            return "[MOCK] No relevant context found."
        context = "\n\n---\n\n".join(
            f"[Chunk {i+1}]\n{chunk}"
            for i, chunk in enumerate(context_chunks)
        )
        return f"[MOCK] Query: {query}\n\nRetrieved context:\n\n{context}"

    def stream_chat(self, query: str, context_chunks: list[str]) -> Iterator[str]:
        full = self.chat(query, context_chunks)
        for word in full.split(" "):
            yield word + " "


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
                        "content": _RAG_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": f"上下文：\n{context}\n\n问题: {query}",
                    },
                ],
                timeout=self._timeout,
            )
            if resp.usage:
                logger.info(
                    "llm.token_usage",
                    extra={
                        "model": self._model,
                        "prompt_tokens": resp.usage.prompt_tokens,
                        "completion_tokens": resp.usage.completion_tokens,
                        "total_tokens": resp.usage.total_tokens,
                    },
                )
            return resp.choices[0].message.content or ""

        return _call()

    def stream_chat(self, query: str, context_chunks: list[str]) -> Iterator[str]:
        context = "\n\n---\n\n".join(context_chunks)
        stream = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": _RAG_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": f"上下文：\n{context}\n\n问题: {query}",
                },
            ],
            timeout=self._timeout,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


class RemoteLLMService:
    """Calls model-service /generate over HTTP. Forwards X-Request-ID for log correlation."""

    def __init__(self, base_url: str, timeout: float):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def chat(self, query: str, context_chunks: list[str]) -> str:
        from app.core.logging import get_request_id

        context = "\n\n---\n\n".join(context_chunks)
        resp = self._client.post(
            f"{self._base_url}/generate",
            json={
                "messages": [
                    {
                        "role": "system",
                        "content": _RAG_SYSTEM_PROMPT,
                    },
                    {"role": "user", "content": f"上下文：\n{context}\n\n问题: {query}"},
                ]
            },
            headers={"X-Request-ID": get_request_id()},
        )
        resp.raise_for_status()
        return resp.json()["content"]

    def stream_chat(self, query: str, context_chunks: list[str]) -> Iterator[str]:
        from app.core.logging import get_request_id

        context = "\n\n---\n\n".join(context_chunks)
        with self._client.stream(
            "POST",
            f"{self._base_url}/generate/stream",
            json={
                "messages": [
                    {
                        "role": "system",
                        "content": _RAG_SYSTEM_PROMPT,
                    },
                    {"role": "user", "content": f"上下文：\n{context}\n\n问题: {query}"},
                ]
            },
            headers={"X-Request-ID": get_request_id()},
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[len("data: "):]
                if data == "[DONE]":
                    break
                payload = json.loads(data)
                if "error" in payload:
                    raise RuntimeError(f"model-service stream error: {payload['error']}")
                yield payload["token"]


class ResilientLLMService:
    """Wraps a primary LLMClient with a fallback. Logs and falls back on any failure."""

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


    def stream_chat(self, query: str, context_chunks: list[str]) -> Iterator[str]:
        from app.core.logging import get_request_id

        try:
            # 初始化迭代器（此时未触发实际请求）
            primary_iter = self._primary.stream_chat(query, context_chunks)
            # next() 触发真实网络请求，若 primary 有问题大概率在此处抛出
            first_token = next(primary_iter)
        except Exception as e:
            logger.warning(
                "Primary stream_chat failed, switching to fallback. "
                "error=%s request_id=%s",
                type(e).__name__,
                get_request_id(),
            )
            yield from self._fallback.stream_chat(query, context_chunks)
            return

        yield first_token
        yield from primary_iter


_instance: LLMClient | None = None

def get_llm_service(settings) -> LLMClient:
    global _instance
    if _instance is None:
        if settings.llm_mode == "mock":
            _instance = MockLLMService()
        elif settings.llm_backend == "remote":
            _instance = ResilientLLMService(
                primary=RemoteLLMService(settings.model_service_url, settings.llm_timeout),
                fallback=MockLLMService(),
            )
        else:
            _instance = ResilientLLMService(
                primary=OpenAILLMService(
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url,
                    model=settings.llm_model,
                    timeout=settings.llm_timeout,
                    max_retries=settings.llm_max_retries,
                ),
                fallback=MockLLMService(),
            )
    return _instance
