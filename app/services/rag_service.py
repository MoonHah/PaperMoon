from app.core.config import settings
from app.services.chunking_service import chunk_text
from app.services.embedding_service import get_embedding_service
from app.services.llm_service import get_llm_service
from app.services.vector_store import get_vector_store
from uuid import uuid4


def upload_document(filename: str, content: str) -> dict:
    chunks = chunk_text(content, chunk_size=settings.chunk_size, overlap=settings.chunk_overlap)
    if not chunks:
        raise ValueError("Document has no extractable content.")

    embedding_client = get_embedding_service(settings)
    embeddings = [embedding_client.embed(chunk) for chunk in chunks]

    document_id = str(uuid4())
    get_vector_store(settings).upsert(document_id, filename, chunks, embeddings)

    return {"document_id": document_id, "filename": filename, "chunk_count": len(chunks)}


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