from app.services.embedding_service import EmbeddingClient
from app.services.vector_store import VectorStore


class SimpleRetriever:
    def __init__(self, embed_client: EmbeddingClient, vector_store: VectorStore):
        self._embed_client = embed_client
        self._vector_store = vector_store
    
    def retrieve(
        self,
        query: str,
        top_k: int,
        user_id: str | None = None,
        document_ids: list[str] | None = None,
    ) -> list[dict]:
        embedding = self._embed_client.embed(query)

        return self._vector_store.search_with_metadata(
            query_embedding=embedding,
            top_k=top_k,
            user_id=user_id,
            document_ids=document_ids,
        )