from app.services.llm_service import LLMClient
from app.services.retrieval.base import Retriever

# 每个候选片段在 prompt 里的最大字符数：太长爆 token 且稀释信号，太短信息不足，300 是平衡点
_CANDIDATE_CHARS = 300


class RerankRetriever:
    """装饰器：包一个 base Retriever，召回 fetch_k 个候选后用 LLM 重排，返回 top_k。

    自身也满足 Retriever 契约，因此能正交地套在 simple/multi_query/hyde 任意策略外面。
    """

    def __init__(
        self,
        base: Retriever,
        llm_client: LLMClient,
        fetch_k: int,
        temperature: float = 0.0,
    ):
        self._base = base
        self._llm = llm_client
        self._fetch_k = fetch_k
        self._temperature = temperature

    def retrieve(self, query: str, top_k: int, user_id: str | None = None) -> list[dict]:
        candidates = self._base.retrieve(query, top_k=self._fetch_k, user_id=user_id)   # 先召回较多
        if len(candidates) <= top_k:
            return candidates           # 候选还没 top_k 多，重排无意义
        order = self._rerank(query, candidates)        # LLM 给出重排后的索引顺序
        return [candidates[i] for i in order][:top_k]  # 按新顺序取前 top_k

    def _rerank(self, query: str, candidates: list[dict]) -> list[int]:
        """用 LLM 对候选做 listwise 重排，返回重排后的索引顺序（如 [2, 0, 3, 1]）。

        一次调用排全部候选（高效）；解析端做满防御，再配两道降级——绝不因 LLM 跑偏而丢候选。
        """
        n = len(candidates)
        listing = "\n".join(
            f"[{i}] {c['text'][:_CANDIDATE_CHARS]}" for i, c in enumerate(candidates)
        )
        prompt = (
            "你是文档相关性排序助手。根据用户问题，对下列候选片段按「对回答该问题的相关性」"
            "从高到低排序。\n\n"
            f"问题：{query}\n\n"
            f"候选片段：\n{listing}\n\n"
            f"要求：只输出片段编号，按相关性从高到低用逗号分隔（例如 3,0,2,1）。"
            f"必须且只包含 0 到 {n - 1} 的全部 {n} 个编号，不要输出任何解释或多余文字。\n"
            "排序结果："
        )

        try:
            raw = self._llm.complete(prompt, temperature=self._temperature)
        except Exception:
            return list(range(n))   # 降级①：LLM 调用失败 → 保持原序（等于不重排）

        # 解析：兼容中文逗号，逐个取合法、去重的索引
        order: list[int] = []
        for tok in raw.replace("，", ",").split(","):
            tok = tok.strip()
            if tok.isdigit():
                idx = int(tok)
                if 0 <= idx < n and idx not in order:
                    order.append(idx)

        if not order:
            return list(range(n))   # 降级②：什么都没解析出来 → 原序

        # 补全缺失：LLM 常只排前几个就收尾，漏掉的按原序附后，保证不丢候选
        for i in range(n):
            if i not in order:
                order.append(i)
        return order
