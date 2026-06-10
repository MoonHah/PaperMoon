import logging
import time
from collections.abc import Iterator

from app.core.config import settings
from app.services.llm_service import get_llm_service
from app.services.retrieval import get_retriever
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def chat(query: str, top_k: int = 3) -> dict:
    vector_store = get_vector_store(settings)
    if vector_store.count() == 0:
        raise ValueError("No documents uploaded yet.")

    t_start = time.perf_counter()

    t_retrieve = time.perf_counter()
    retriever = get_retriever(settings)
    retrieved_chunks = [c["text"] for c in retriever.retrieve(query, top_k=top_k)]
    retrieval_latency_ms = round((time.perf_counter() - t_retrieve) * 1000, 2)

    t_llm = time.perf_counter()
    llm_client = get_llm_service(settings)
    answer = llm_client.chat(query, retrieved_chunks)
    llm_latency_ms = round((time.perf_counter() - t_llm) * 1000, 2)

    total_latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

    logger.info(
        "rag.chat",
        extra={
            "retrieved_chunk_count": len(retrieved_chunks),
            "retrieval_latency_ms": retrieval_latency_ms,
            "llm_latency_ms": llm_latency_ms,
            "total_latency_ms": total_latency_ms,
            "model": settings.llm_model if settings.llm_mode == "openai" else "mock",
        },
    )

    return {"answer": answer, "retrieved_chunks": retrieved_chunks}




def stream_chat(query: str, top_k: int = 3) -> Iterator[str]:
    vector_store = get_vector_store(settings)
    if vector_store.count() == 0:
        raise ValueError("No documents uploaded yet.")

    t_start = time.perf_counter()

    t_retrieve = time.perf_counter()
    retriever = get_retriever(settings)
    retrieved_chunks = [c["text"] for c in retriever.retrieve(query, top_k=top_k)]
    retrieval_latency_ms = round((time.perf_counter() - t_retrieve) * 1000, 2)

    t_llm = time.perf_counter()
    llm_client = get_llm_service(settings)
    yield from llm_client.stream_chat(query, retrieved_chunks)
    llm_latency_ms = round((time.perf_counter() - t_llm) * 1000, 2)

    total_latency_ms = round((time.perf_counter() - t_start) * 1000, 2)

    logger.info(
        "rag.stream_chat",
        extra={
            "retrieved_chunk_count": len(retrieved_chunks),
            "retrieval_latency_ms": retrieval_latency_ms,
            "llm_latency_ms": llm_latency_ms,
            "total_latency_ms": total_latency_ms,
            "model": settings.llm_model if settings.llm_mode == "openai" else "mock",
        },
    )


