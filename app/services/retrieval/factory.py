from app.services.embedding_service import get_embedding_service
from app.services.llm_service import get_llm_service
from app.services.retrieval.base import Retriever
from app.services.retrieval.hyde import HyDERetriever
from app.services.retrieval.multi_query import MultiQueryRetriever
from app.services.retrieval.simple import SimpleRetriever
from app.services.vector_store import get_vector_store


def get_retriever(
    settings, mode: str | None = None, temperature: float | None = None
) -> Retriever:
    """按检索模式组装一个 Retriever。

    mode 为 None 时读取 settings.retrieval_mode；显式传入可临时覆盖（评估脚本用）。
    temperature 为 None 时读取 settings.retrieval_temperature；仅对含 LLM 的策略
    （multi_query / hyde）生效，simple 不涉及 LLM 故不传。

    刻意不做单例缓存：Retriever 只是轻量策略包装，重资源（embedding/向量库/LLM 客户端）
    已各自单例，这里每次新建几乎零开销，却能让评估脚本在同进程里自由切换策略与温度。
    """
    mode = mode or settings.retrieval_mode
    temp = settings.retrieval_temperature if temperature is None else temperature

    if mode == "simple":
        return SimpleRetriever(
            embed_client=get_embedding_service(settings),
            vector_store=get_vector_store(settings),
        )
    elif mode == "multi_query":
        return MultiQueryRetriever(
            embed_client=get_embedding_service(settings),
            vector_store=get_vector_store(settings),
            llm_client=get_llm_service(settings),
            query_count=settings.multi_query_count,
            temperature=temp,
        )
    elif mode == "hyde":
        return HyDERetriever(
            embed_client=get_embedding_service(settings),
            vector_store=get_vector_store(settings),
            llm_client=get_llm_service(settings),
            temperature=temp,
        )
    else:
        raise ValueError(
            f"Unknown retrieval_mode: {mode!r} (supported: 'simple', 'multi_query', 'hyde')"
        )
