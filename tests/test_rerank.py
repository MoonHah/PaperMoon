"""RerankRetriever 测试——用假对象，零 API、零外部依赖。

_rerank（解析/补全/降级）直接测，不受 retrieve 的 top_k 截断与跳过逻辑干扰；
retrieve 的召回/截断/跳过单独测。
"""

from app.services.retrieval.rerank import RerankRetriever


class _FakeBase:
    """假 base Retriever：返回固定候选（text 可识别，便于断言顺序）。"""

    def __init__(self, n: int):
        self._docs = [
            {"text": f"doc-{i}", "document_id": str(i), "filename": "f"} for i in range(n)
        ]

    def retrieve(
        self,
        query: str,
        top_k: int,
        user_id: str | None = None,
        document_ids: list[str] | None = None,
    ) -> list[dict]:
        return self._docs[:top_k]


class _FakeLLM:
    """假 LLM：complete 吐预设排序字符串（或抛异常模拟失败）。"""

    def __init__(self, response: str | None = None, raise_exc: bool = False):
        self._response = response
        self._raise = raise_exc

    def complete(self, prompt: str, temperature: float = 0.0) -> str:
        if self._raise:
            raise RuntimeError("llm down")
        return self._response or ""


def _candidates(n: int) -> list[dict]:
    return [{"text": f"doc-{i}", "document_id": str(i), "filename": "f"} for i in range(n)]


def _rr(llm: _FakeLLM) -> RerankRetriever:
    return RerankRetriever(base=_FakeBase(0), llm_client=llm, fetch_k=5)


# ── _rerank：解析 / 补全 / 降级 ──────────────────────────────────────

def test_rerank_normal_order():
    assert _rr(_FakeLLM("2,0,1"))._rerank("q", _candidates(3)) == [2, 0, 1]


def test_rerank_completes_missing():
    # LLM 只排了前两个，漏掉的 1,3,4 按原序补在后面（不丢候选）
    assert _rr(_FakeLLM("2,0"))._rerank("q", _candidates(5)) == [2, 0, 1, 3, 4]


def test_rerank_chinese_comma_and_invalid_tolerated():
    # 兼容中文逗号；越界(9)与重复(第二个1)被忽略；缺失(2)补全
    assert _rr(_FakeLLM("1，9，1，0"))._rerank("q", _candidates(3)) == [1, 0, 2]


def test_rerank_empty_degrades_to_original():
    assert _rr(_FakeLLM("模型废话没有编号"))._rerank("q", _candidates(4)) == [0, 1, 2, 3]


def test_rerank_llm_failure_degrades_to_original():
    assert _rr(_FakeLLM(raise_exc=True))._rerank("q", _candidates(4)) == [0, 1, 2, 3]


# ── retrieve：召回 / 重排截断 / 跳过 ─────────────────────────────────

def test_retrieve_reorders_and_truncates():
    r = RerankRetriever(base=_FakeBase(5), llm_client=_FakeLLM("2,0,1,3,4"), fetch_k=5)
    out = r.retrieve("q", top_k=2)   # 召回 5 → 重排 → 取前 2
    assert [d["text"] for d in out] == ["doc-2", "doc-0"]


def test_retrieve_skips_rerank_when_candidates_not_more_than_top_k():
    # 召回数(2) <= top_k(3) → 跳过重排，LLM 不该被调用（设成会抛，验证确实没调）
    r = RerankRetriever(base=_FakeBase(2), llm_client=_FakeLLM(raise_exc=True), fetch_k=2)
    out = r.retrieve("q", top_k=3)
    assert [d["text"] for d in out] == ["doc-0", "doc-1"]
