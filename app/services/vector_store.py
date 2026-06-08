from typing import Protocol
from uuid import uuid4

class VectorStore(Protocol):
    def ensure_collection(self) -> None: ...
    def upsert(self, document_id: str, filename: str, chunks: list[str], embeddings: list[list[float]]) -> None: ...
    def delete_by_document_id(self, document_id: str) -> None: ...
    def search(self, query_embedding: list[float], top_k: int) -> list[str]: ...
    def search_with_metadata(self, query_embedding: list[float], top_k: int) -> list[dict]: ...
    def count(self) -> int: ...



# Initialize QdrantVectorStore
class QdrantVectorStore:
    def __init__(self, url: str, collection: str, vector_size: int, timeout: int = 5):
        from qdrant_client import QdrantClient

        self._collection = collection
        self._vector_size = vector_size
        try:
            self._client = QdrantClient(url=url, timeout=timeout)
        except Exception as e:
            raise RuntimeError(f"Cannot connect to Qdrant at {url}: {e}")

    # 确定目标集合存在
    def ensure_collection(self) -> None:
        from qdrant_client.models import Distance, VectorParams

        # 1. 先获取数据库中所有已存在的集合名
        existing = {c.name for c in self._client.get_collections().collections}
        # 2. 若不存在，就创建一个新集合，向量配置为指定维度、采用余弦相似度作为距离度量
        if self._collection not in existing:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(
                    size=self._vector_size,
                    distance=Distance.COSINE,
                ),
            )

    def upsert(self,
               document_id: str,
               filename: str,
               chunks: list[str],
               embeddings: list[list[float]]) -> None:
        from qdrant_client.models import PointStruct

        points = [
            PointStruct(
                id=str(uuid4()),
                vector=embedding,
                # 因为当前没有 PostgreSQL, chunk 的原文先直接存在 Qdrant payload 中, search 时从payload 返回
                payload={
                    "document_id": document_id,
                    "filename": filename,
                    "chunk_text": chunk,
                },
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]
        self._client.upsert(collection_name=self._collection, points=points)
    
    def delete_by_document_id(self, document_id: str) -> None:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        self._client.delete(
            collection_name=self._collection,
            points_selector=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
            ),
        )

    def search(self, query_embedding: list[float], top_k: int) -> list[str]:
        results = self._client.query_points(
            collection_name=self._collection,
            query=query_embedding,
            limit=top_k,
        )
        return [
            hit.payload["chunk_text"]
            for hit in results.points
            if hit.payload and "chunk_text" in hit.payload #
        ]

    def search_with_metadata(self, query_embedding: list[float], top_k: int) -> list[dict]:
        results = self._client.query_points(
            collection_name=self._collection,
            query=query_embedding,
            limit=top_k,
        )
        return [
            {
                "text": hit.payload["chunk_text"],
                "document_id": hit.payload["document_id"],
                "filename": hit.payload["filename"],
            }
            for hit in results.points
            if hit.payload and "chunk_text" in hit.payload
        ]

    def count(self) -> int:
        return self._client.count(collection_name=self._collection).count


# 懒加载单例
_instance: QdrantVectorStore | None = None

def get_vector_store(settings) -> VectorStore:
    global _instance
    if _instance is None:
        _instance = QdrantVectorStore(
            url=settings.qdrant_url,
            collection=settings.qdrant_collection,
            vector_size=settings.vector_size,
            timeout=settings.qdrant_timeout,
        )
    return _instance

