import logging
import time
from collections.abc import Iterator

from app.core.config import settings
from app.services.llm_service import get_llm_service
from app.services.retrieval import get_retriever
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def _ensure_documents_exist() -> None:
    if get_vector_store(settings).count() == 0:
        raise ValueError("No documents uploaded yet.")


def _retrieve(query: str, top_k: int, user_id: str) -> tuple[list[str], float]:
    """检索 + 计时，返回 (chunk 文本列表, 检索耗时 ms)。chat / stream_chat 共用。"""
    t = time.perf_counter()
    chunks = [
        c["text"]
        for c in get_retriever(settings).retrieve(query, top_k=top_k, user_id=user_id)
    ]
    latency_ms = round((time.perf_counter() - t) * 1000, 2)
    return chunks, latency_ms


def _model_label() -> str:
    return settings.llm_model if settings.llm_mode == "openai" else "mock"


def chat(query: str, top_k: int, user_id: str) -> dict:
    _ensure_documents_exist()
    t_start = time.perf_counter()

    retrieved_chunks, retrieval_latency_ms = _retrieve(query, top_k, user_id)

    t_llm = time.perf_counter()
    answer = get_llm_service(settings).chat(query, retrieved_chunks)
    llm_latency_ms = round((time.perf_counter() - t_llm) * 1000, 2)

    total_latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
    logger.info(
        "rag.chat",
        extra={
            "retrieved_chunk_count": len(retrieved_chunks),
            "retrieval_latency_ms": retrieval_latency_ms,
            "llm_latency_ms": llm_latency_ms,
            "total_latency_ms": total_latency_ms,
            "model": _model_label(),
        },
    )
    return {"answer": answer, "retrieved_chunks": retrieved_chunks}


def stream_chat(query: str, top_k: int, user_id: str) -> Iterator[str]:
    _ensure_documents_exist()
    t_start = time.perf_counter()

    retrieved_chunks, retrieval_latency_ms = _retrieve(query, top_k, user_id)

    t_llm = time.perf_counter()
    yield from get_llm_service(settings).stream_chat(query, retrieved_chunks)
    llm_latency_ms = round((time.perf_counter() - t_llm) * 1000, 2)

    total_latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
    logger.info(
        "rag.stream_chat",
        extra={
            "retrieved_chunk_count": len(retrieved_chunks),
            "retrieval_latency_ms": retrieval_latency_ms,
            "llm_latency_ms": llm_latency_ms,
            "total_latency_ms": total_latency_ms,
            "model": _model_label(),
        },
    )
