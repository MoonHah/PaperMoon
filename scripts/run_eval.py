"""
RAG 检索质量离线评估脚本

用法：
    python scripts/run_eval.py                   # 默认 top_k=3
    python scripts/run_eval.py --top-k 5         # 调整检索数量
    python scripts/run_eval.py --questions path/to/custom.json

指标说明：
    Hit Rate — top_k 结果中，至少一个 chunk 包含期望关键词的比例
    MRR      — Mean Reciprocal Rank，第一个命中 chunk 排名的倒数均值

前置条件：
    1. Qdrant 正在运行（docker compose up qdrant）
    2. 至少已上传一篇文档（状态为 READY）
    3. 从项目根目录运行：python scripts/run_eval.py
"""

import argparse
import json
import os
import sys
from pathlib import Path

# 绕过本地地址的系统代理：
# macOS 系统代理（如 Clash）会让 httpx 把发往 localhost 的请求也转发给代理，
# 导致连接 Qdrant 超时。必须在创建任何 httpx 客户端（QdrantClient）之前设置。
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")

# 让脚本能 import app.*（从项目根目录运行时生效）
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.services.vector_store import get_vector_store
from app.services.retrieval import get_retriever

COL_W = 50  # 问题列宽度


def evaluate(questions: list[dict], top_k: int, retrieval_mode: str | None) -> None:
    # mock embedding 下结果无意义，给出明显警告但不中止
    if settings.embedding_mode == "mock":
        print("WARNING: embedding_mode=mock — 检索结果基于随机哈希，数字无参考价值。")
        print("         请在 .env 中设置 EMBEDDING_MODE=openai 后重新运行。\n")

    try:
        vector_store = get_vector_store(settings)
        chunk_count = vector_store.count()
    except Exception as e:
        print(f"ERROR: 无法连接 Qdrant — {e}")
        print("       请先运行：docker compose up -d qdrant")
        sys.exit(1)

    if chunk_count == 0:
        print("ERROR: Qdrant 集合为空，请先上传文档。")
        sys.exit(1)

    mode = retrieval_mode or settings.retrieval_mode
    retriever = get_retriever(settings, mode=mode)

    print(f"集合中共有 {chunk_count} 个 chunk，开始评估（top_k={top_k}, retrieval_mode={mode}）\n")

    hits = 0
    reciprocal_ranks: list[float] = []

    print(f"{'Question':<{COL_W}} {'Hit':<5} {'Rank'}")
    print("-" * (COL_W + 12))

    for item in questions:
        question: str = item["question"]
        keywords: list[str] = [kw.lower() for kw in item["expected_keywords"]]

        chunks = retriever.retrieve(question, top_k=top_k)

        first_hit_rank: int | None = None
        for rank, chunk in enumerate(chunks, start=1):
            if any(kw in chunk["text"].lower() for kw in keywords):
                first_hit_rank = rank
                break

        if first_hit_rank is not None:
            hits += 1
            reciprocal_ranks.append(1.0 / first_hit_rank)
        else:
            reciprocal_ranks.append(0.0)

        hit_marker = "✓" if first_hit_rank else "✗"
        rank_str = str(first_hit_rank) if first_hit_rank else "-"
        display_q = question[: COL_W - 2] + ".." if len(question) > COL_W else question
        print(f"{display_q:<{COL_W}} {hit_marker:<5} {rank_str}")

    total = len(questions)
    hit_rate = hits / total if total > 0 else 0.0
    mrr = sum(reciprocal_ranks) / total if total > 0 else 0.0

    print("-" * (COL_W + 12))
    print(f"Hit Rate : {hits}/{total} = {hit_rate:.1%}")
    print(f"MRR      : {mrr:.4f}")
    print(f"top_k    : {top_k}")


def main() -> None:
    parser = argparse.ArgumentParser(description="评估 RAG 检索质量（Hit Rate + MRR）")
    parser.add_argument(
        "--questions",
        type=Path,
        default=Path(__file__).parent / "baseline_questions.json",
        help="问题集 JSON 文件路径（默认：scripts/baseline_questions.json）",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="检索返回的 chunk 数量（默认：3）",
    )
    parser.add_argument(
        "--retrieval-mode",
        type=str,
        default=None,
        help="检索策略: simple | multi_query (默认读 settings.retrieval_mode)"
    )
    args = parser.parse_args()

    if not args.questions.exists():
        print(f"ERROR: 找不到问题集文件：{args.questions}")
        sys.exit(1)

    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    print(f"已加载 {len(questions)} 道问题 ← {args.questions}\n")
    evaluate(questions, args.top_k, args.retrieval_mode)


if __name__ == "__main__":
    main()
