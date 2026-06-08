import logging
from typing import Protocol

import numpy as np
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


class EmbeddingClient(Protocol):
    def embed(self, text: str) -> list[float]: ...


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


class OpenAIEmbeddingService:
    def __init__(self, api_key: str, base_url: str, model: str, timeout: float, max_retries: int):
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries

    def embed(self, text: str) -> list[float]:
        @retry(
            retry=retry_if_exception_type(_RETRY_ON),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            stop=stop_after_attempt(self._max_retries),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        def _call() -> list[float]:
            resp = self._client.embeddings.create(
                input=text,
                model=self._model,
                timeout=self._timeout,
            )
            return resp.data[0].embedding

        return _call()


def get_embedding_service(settings) -> EmbeddingClient:
    if settings.embedding_mode == "mock":
        return MockEmbeddingService()
    return OpenAIEmbeddingService(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.embedding_model,
        timeout=settings.embedding_timeout,
        max_retries=settings.embedding_max_retries,
    )
