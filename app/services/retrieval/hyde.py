from app.services.embedding_service import EmbeddingClient
from app.services.llm_service import LLMClient
from app.services.vector_store import VectorStore


class HyDERetriever:
    def __init__(
        self,
        embed_client: EmbeddingClient,
        vector_store: VectorStore,
        llm_client: LLMClient,
        temperature: float = 0.0,
    ):
        self._embed_client = embed_client
        self._vector_store = vector_store
        self._llm_client = llm_client
        self._temperature = temperature

    def _generate_hypothesis(self, query: str) -> str:
        prompt = (
            "请直接写一段用于回答下面问题的文档段落，像学术论文或技术文档的正文那样陈述，"
            "尽量使用相关的专业术语和概念。不要说'我不确定'或'据我所知'，不要反问，直接写正文。"
            "请使用与问题相同的语言书写。\n\n"
            f"问题：{query}"
        )
        try:
            return self._llm_client.complete(prompt, temperature=self._temperature).strip()
        except Exception:
            return ""

    def retrieve(self, query: str, top_k: int) -> list[dict]:
        hypothesis = self._generate_hypothesis(query)
        # 假设答案为空（mock 或生成失败）时退回原 query 检索 = simple 行为，绝不崩
        text_to_embed = hypothesis if hypothesis else query
        embedding = self._embed_client.embed(text_to_embed)
        return self._vector_store.search_with_metadata(embedding, top_k=top_k)
