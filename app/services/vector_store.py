from typing import Protocol
from uuid import uuid4

class VectorStore(Protocol):
    def ensure_collection(self) -> None: ...
    def upsert(self, document_id: str, user_id: str, filename: str, chunks: list[str], embeddings: list[list[float]]) -> None: ...
    def delete_by_document_id(self, document_id: str) -> None: ...
    def search_with_metadata(self, query_embedding: list[float], top_k: int, user_id: str | None = None, document_ids: list[str] | None = None) -> list[dict]: ...
    def count(self, user_id: str | None = None) -> int: ...



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
               user_id: str,
               filename: str,
               chunks: list[str],
               embeddings: list[list[float]]) -> None:
        from qdrant_client.models import PointStruct

        points = [
            PointStruct(
                id=str(uuid4()),
                vector=embedding,
                payload={
                    "document_id": document_id,
                    "user_id": user_id,        # 多租户：检索时按它过滤
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

    def search_with_metadata(
        self,
        query_embedding: list[float],
        top_k: int,
        user_id: str | None = None,
        document_ids: list[str] | None = None,
    ) -> list[dict]:
        from qdrant_client.models import Filter, FieldCondition, MatchAny, MatchValue

        # 组合过滤（AND）：user_id 做多租户隔离，document_ids 做对话范围限定。
        # user_id 为 None 不过滤（离线评估等无用户上下文场景）；document_ids 为空不限定范围。
        must = []
        if user_id is not None:
            must.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))
        if document_ids:
            must.append(FieldCondition(key="document_id", match=MatchAny(any=document_ids)))
        query_filter = Filter(must=must) if must else None
        results = self._client.query_points(
            collection_name=self._collection,
            query=query_embedding,
            limit=top_k,
            query_filter=query_filter,
        )
        return [
            {
                "text": hit.payload["chunk_text"],
                "document_id": hit.payload.get("document_id", ""),
                "filename": hit.payload.get("filename", ""),
            }
            for hit in results.points
            if hit.payload and "chunk_text" in hit.payload
        ]

    def count(self, user_id: str | None = None) -> int:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        count_filter = (
            Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])
            if user_id is not None
            else None
        )
        return self._client.count(
            collection_name=self._collection, count_filter=count_filter
        ).count


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

