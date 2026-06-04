import numpy as np
from dataclasses import dataclass
from uuid import uuid4


@dataclass
class DocumentRecord:
    document_id: str
    filename: str
    chunk_count: int


@dataclass
class ChunkRecord:
    document_id: str
    chunk_text: str
    embedding: list[float]


class MemoryStore:
    def __init__(self):
        self._documents: dict[str, DocumentRecord] = {}
        self._chunks: list[ChunkRecord] = []

    def add_document(self, filename: str, chunks: list[str], embeddings: list[list[float]]) -> str:
        document_id = str(uuid4())
        self._documents[document_id] = DocumentRecord(
            document_id=document_id,
            filename=filename,
            chunk_count=len(chunks),
        )
        for chunk, embedding in zip(chunks, embeddings):
            self._chunks.append(ChunkRecord(
                document_id=document_id,
                chunk_text=chunk,
                embedding=embedding,
            ))
        return document_id

    def search(self, query_embedding: list[float], top_k: int = 3) -> list[str]:
        if not self._chunks:
            return []
        q = np.array(query_embedding)
        chunk_matrix = np.array([c.embedding for c in self._chunks])
        scores = chunk_matrix @ q                        # 向量已归一化，点积即余弦相似度
        top_indices = np.argsort(scores)[::-1][:top_k]  # 从高到低取 top_k 个下标
        return [self._chunks[i].chunk_text for i in top_indices]

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)


# 全局单例：Phase 1 单进程，所有请求共享同一个内存存储
memory_store = MemoryStore()
