import logging
from typing import Protocol

import httpx
import numpy as np
import openai

from app.services._openai_retry import openai_retry

logger = logging.getLogger(__name__)


class EmbeddingClient(Protocol):
    def embed(self, text: str) -> list[float]: ...
    # 批量嵌入：一次嵌入多个文本，返回与输入等长、同序的向量列表。索引时用它替代逐条 embed。
    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class MockEmbeddingService:
    DIM = 256

    def embed(self, text: str) -> list[float]:
        vec = np.zeros(self.DIM)
        for word in text.lower().split():
            idx = hash(word) % self.DIM
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


class OpenAIEmbeddingService:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        max_retries: int,
        batch_size: int = 128,
    ):
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries
        self._batch_size = batch_size

    def embed(self, text: str) -> list[float]:
        @openai_retry(self._max_retries, logger)
        def _call() -> list[float]:
            resp = self._client.embeddings.create(
                input=text,
                model=self._model,
                timeout=self._timeout,
            )
            return resp.data[0].embedding

        return _call()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # 一次请求嵌入一组文本，按 batch_size 子批以避免超单请求 token 上限。
        # 按 data.index 排序回原序（OpenAI 以 index 标位，防乱序）。
        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            sub = texts[i : i + self._batch_size]

            @openai_retry(self._max_retries, logger)
            def _call(batch: list[str] = sub) -> list[list[float]]:
                resp = self._client.embeddings.create(
                    input=batch,
                    model=self._model,
                    timeout=self._timeout,
                )
                ordered = sorted(resp.data, key=lambda d: d.index)
                return [d.embedding for d in ordered]

            out.extend(_call())
        return out


class RemoteEmbeddingService:
    """Calls model-service /embed over HTTP. Forwards X-Request-ID for log correlation."""

    def __init__(self, base_url: str, timeout: float):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def embed(self, text: str) -> list[float]:
        from app.core.logging import get_request_id

        resp = self._client.post(
            f"{self._base_url}/embed",
            json={"text": text},
            headers={"X-Request-ID": get_request_id()},
        )
        resp.raise_for_status()
        return resp.json()["embedding"]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # model-service 仅暴露单条 /embed，故客户端逐条循环（remote 是 opt-in 后端，
        # 若大量使用可在 model-service 加 /embed/batch 端点再优化）。
        return [self.embed(t) for t in texts]


_instance: EmbeddingClient | None = None


def get_embedding_service(settings) -> EmbeddingClient:
    global _instance
    if _instance is None:
        if settings.embedding_mode == "mock":
            _instance = MockEmbeddingService()
        elif settings.embedding_backend == "remote":
            _instance = RemoteEmbeddingService(
                settings.model_service_url, settings.embedding_timeout
            )
        else:
            _instance = OpenAIEmbeddingService(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model=settings.embedding_model,
                timeout=settings.embedding_timeout,
                max_retries=settings.embedding_max_retries,
                batch_size=settings.embedding_batch_size,
            )
    return _instance
