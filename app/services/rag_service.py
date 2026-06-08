from app.core.config import settings

from app.services.embedding_service import get_embedding_service
from app.services.llm_service import get_llm_service
from app.services.vector_store import get_vector_store

def chat(query: str, top_k: int = 3) -> dict:
    vector_store = get_vector_store(settings)
    if vector_store.count() == 0:
        raise ValueError("No documents uploaded yet.")

    embedding_client = get_embedding_service(settings)
    query_embedding = embedding_client.embed(query)
    retrieved_chunks = vector_store.search(query_embedding, top_k=top_k)

    llm_client = get_llm_service(settings)
    answer = llm_client.chat(query, retrieved_chunks)
    return {"answer": answer, "retrieved_chunks": retrieved_chunks}
