from app.services.retrieval.base import Retriever
from app.services.retrieval.simple import SimpleRetriever
from app.services.retrieval.multi_query import MultiQueryRetriever
from app.services.llm_service import get_llm_service
from app.services.embedding_service import get_embedding_service
from app.services.vector_store import get_vector_store


def get_retriever(settings, mode: str | None = None) -> Retriever:
    mode = mode or settings.retrieval_mode

    if mode == "simple":
        embed_client = get_embedding_service(settings)
        vector_store = get_vector_store(settings)
        return SimpleRetriever(embed_client, vector_store)
    elif mode == "multi_query":
        return MultiQueryRetriever(
            embed_client=get_embedding_service(settings),
            vector_store=get_vector_store(settings),
            llm_client=get_llm_service(settings),
            query_count=settings.multi_query_count,
        )
    else:
        raise ValueError(f"Unknown retrieval_mode: {mode!r} (supported: 'simple', 'multi_query')")
    

