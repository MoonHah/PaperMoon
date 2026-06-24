"""对话范围限定：document_ids 经 Retriever 透传到向量库并如实过滤。

只验检索 mechanics（用 InMemoryVectorStore），多租户 user_id 过滤仍在真实 Qdrant 端到端验证。
"""

from app.services.retrieval.simple import SimpleRetriever
from tests.conftest import InMemoryVectorStore


class _FakeEmbed:
    """InMemoryVectorStore 忽略 embedding，返回任意向量即可。"""

    def embed(self, text: str) -> list[float]:
        return [0.0]


def _store_with_two_docs() -> InMemoryVectorStore:
    store = InMemoryVectorStore()
    store.upsert("d1", "a.pdf", ["chunk a1", "chunk a2"], [[0.0], [0.0]])
    store.upsert("d2", "b.pdf", ["chunk b1"], [[0.0]])
    return store


def test_no_scope_returns_all_documents():
    r = SimpleRetriever(embed_client=_FakeEmbed(), vector_store=_store_with_two_docs())
    hits = r.retrieve("q", top_k=10)
    assert {h["document_id"] for h in hits} == {"d1", "d2"}
    assert len(hits) == 3


def test_scope_filters_to_selected_documents():
    r = SimpleRetriever(embed_client=_FakeEmbed(), vector_store=_store_with_two_docs())
    hits = r.retrieve("q", top_k=10, document_ids=["d1"])
    assert {h["document_id"] for h in hits} == {"d1"}
    assert len(hits) == 2


def test_empty_scope_is_treated_as_no_scope():
    # graph_agent.run 把空列表归一成 None；这里直接传空列表也应不过滤（与向量库 `if document_ids` 一致）
    r = SimpleRetriever(embed_client=_FakeEmbed(), vector_store=_store_with_two_docs())
    hits = r.retrieve("q", top_k=10, document_ids=[])
    assert len(hits) == 3
