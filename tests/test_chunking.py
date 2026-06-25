"""结构感知分块（chunk_text）单测：边界尊重 + 尺寸约束 + 空/短输入 + 确定性。

重点验证「结构感知」相对朴素定长切的改进：中文在句末标点处切，不从句子/词中间断开。
"""

from app.services.chunking_service import chunk_text

# 6 句中文，每句约 20 字，每句以 。 结尾
_ZH_TEXT = "".join(f"这是第{i}句用于测试分块边界的中文句子内容。" for i in range(1, 7))


def test_empty_and_whitespace_return_empty():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_short_text_single_chunk():
    assert chunk_text("短文本。", chunk_size=50, overlap=10) == ["短文本。"]


def test_chunks_respect_size_limit():
    chunks = chunk_text(_ZH_TEXT, chunk_size=50, overlap=10)
    assert len(chunks) > 1                     # 126 字 / 50 → 必然多块
    assert all(len(c) <= 50 for c in chunks)   # 每块不超过 chunk_size


def test_splits_at_sentence_boundary_not_mid_sentence():
    # 结构感知核心：中文按句末「。」切，不从句子中间断开。
    # 文本以「。」结尾，故每一块都应以「。」收尾（朴素定长切会从字中间断）。
    chunks = chunk_text(_ZH_TEXT, chunk_size=50, overlap=10)
    assert all(c.endswith("。") for c in chunks)


def test_all_chunks_nonempty_and_stripped():
    chunks = chunk_text(_ZH_TEXT, chunk_size=40, overlap=5)
    assert all(c == c.strip() and c for c in chunks)


def test_deterministic():
    a = chunk_text(_ZH_TEXT, chunk_size=50, overlap=10)
    b = chunk_text(_ZH_TEXT, chunk_size=50, overlap=10)
    assert a == b
