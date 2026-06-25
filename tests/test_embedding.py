"""嵌入服务 embed_batch 单测：批量结果与逐条一致、等长、保序。

只验 Mock 实现（测试默认 EMBEDDING_MODE=mock）；OpenAI 真批量靠 e2e/真实 API，
但 worker 索引经 embed_batch 走通由 test_task 间接覆盖。
"""

from app.services.embedding_service import MockEmbeddingService


def test_embed_batch_matches_single():
    svc = MockEmbeddingService()
    texts = ["hello world", "foo bar baz", "another chunk"]
    batched = svc.embed_batch(texts)
    assert batched == [svc.embed(t) for t in texts]   # 与逐条一致


def test_embed_batch_length_and_order():
    svc = MockEmbeddingService()
    texts = ["a", "b b", "c c c"]
    out = svc.embed_batch(texts)
    assert len(out) == len(texts)                      # 等长
    # 保序：每个向量应等于对应单条的嵌入（顺序未被打乱）
    for text, vec in zip(texts, out):
        assert vec == svc.embed(text)


def test_embed_batch_empty():
    assert MockEmbeddingService().embed_batch([]) == []
