import numpy as np

from typing import Protocol  # 鸭子类型


class EmbeddingClient(Protocol):
    def embed(self, text: str) -> list[float]: ...

# Mock Embedding by Hash
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


# OpenAI Embedding
class OpenAIEmbeddingService:
    def __init__(self, api_key: str, base_url: str, model: str):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
    
    def embed(self, text: str) -> list[float]:
        resp = self.client.embeddings.create(
            input=text,
            model=self.model,
            timeout=10.0,  # 所有外部 API 调用必须有, 防止网络问题导致请求永久挂起
        )
        return resp.data[0].embedding


def get_embedding_service(settings) -> EmbeddingClient:
    if settings.embedding_mode == "mock":
        return MockEmbeddingService()
    return OpenAIEmbeddingService(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.embedding_model,
    )