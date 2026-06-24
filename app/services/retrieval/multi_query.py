from itertools import zip_longest

from app.services.embedding_service import EmbeddingClient
from app.services.llm_service import LLMClient
from app.services.vector_store import VectorStore


class MultiQueryRetriever:
    def __init__(
        self,
        embed_client: EmbeddingClient,
        vector_store: VectorStore,
        llm_client: LLMClient,
        query_count: int,
        temperature: float = 0.0,
    ) -> None:
        self._embed_client = embed_client
        self._vector_store = vector_store
        self._llm_client = llm_client
        self._query_count = query_count
        self._temperature = temperature

    def _rewrite(self, query: str) -> list[str]:
        # 1. 构造 prompt & 调用 LLM
        prompt = (
            f"你是检索查询改写助手。请把下面的问题改写成 {self._query_count} 个"
            "语义相同但措辞/角度不同的检索查询。\n"
            "要求：每行输出一个查询，只输出查询本身，不要编号、不要解释。\n\n"
            f"问题：{query}"
        )
        try:
            raw = self._llm_client.complete(prompt, temperature=self._temperature)
        except Exception:
            return [query]         # LLM 调用失败 -> 退回只用原始 query

        # 2. 解析清洗
        rewrites = []
        for line in raw.splitlines():
            line = line.strip().lstrip("0123456789.-、) ").strip()  # 去空白 + 去可能的序号前缀
            if line:
                rewrites.append(line)

        # 3. 合并 query 并去重（保序）
        return list(dict.fromkeys([query, *rewrites]))

    def retrieve(
        self,
        query: str,
        top_k: int,
        user_id: str | None = None,
        document_ids: list[str] | None = None,
    ) -> list[dict]:
        queries = self._rewrite(query)

        # 1. 多路检索
        results_per_query = []
        for q in queries:
            embedding = self._embed_client.embed(q)
            hits = self._vector_store.search_with_metadata(
                embedding, top_k=top_k, user_id=user_id, document_ids=document_ids
            )
            results_per_query.append(hits)

        # 2. round-robin 合并去重截断
        merged, seen = [], set()
        for rank_layer in zip_longest(*results_per_query):
            for chunk in rank_layer:
                if chunk is None or chunk["text"] in seen:
                    continue
                seen.add(chunk["text"])
                merged.append(chunk)

        return merged[:top_k]
