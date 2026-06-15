from app.services.embedding_service import get_embedding_service
from app.services.llm_service import get_llm_service
from app.services.retrieval.base import Retriever
from app.services.retrieval.hyde import HyDERetriever
from app.services.retrieval.multi_query import MultiQueryRetriever
from app.services.retrieval.rerank import RerankRetriever
from app.services.retrieval.simple import SimpleRetriever
from app.services.vector_store import get_vector_store


def get_retriever(
    settings, mode: str | None = None, temperature: float | None = None
) -> Retriever:
    """按检索模式组装一个 Retriever，并按需叠加 Reranking 装饰。

    mode 为 None 时读取 settings.retrieval_mode；temperature 为 None 时读取
    settings.retrieval_temperature。rerank 是正交开关（settings.rerank_enabled），
    开启时包在任意 base 策略外面——这是 Retriever 抽象 + 装饰器模式的回报。
    """
    mode = mode or settings.retrieval_mode
    temp = settings.retrieval_temperature if temperature is None else temperature

    if mode == "simple":
        base: Retriever = SimpleRetriever(
            embed_client=get_embedding_service(settings),
            vector_store=get_vector_store(settings),
        )
    elif mode == "multi_query":
        base = MultiQueryRetriever(
            embed_client=get_embedding_service(settings),
            vector_store=get_vector_store(settings),
            llm_client=get_llm_service(settings),
            query_count=settings.multi_query_count,
            temperature=temp,
        )
    elif mode == "hyde":
        base = HyDERetriever(
            embed_client=get_embedding_service(settings),
            vector_store=get_vector_store(settings),
            llm_client=get_llm_service(settings),
            temperature=temp,
        )
    else:
        raise ValueError(
            f"Unknown retrieval_mode: {mode!r} (supported: 'simple', 'multi_query', 'hyde')"
        )

    # Reranking 正交装饰：召回 fetch_k 个候选 → LLM 重排 → 截断 top_k
    if settings.rerank_enabled:
        return RerankRetriever(
            base=base,
            llm_client=get_llm_service(settings),
            fetch_k=settings.rerank_fetch_k,
            temperature=temp,
        )
    return base
