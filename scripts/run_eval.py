"""
RAG 检索质量离线评估脚本

用法：
    python scripts/run_eval.py                                          # simple, top_k=3, 跑1次
    python scripts/run_eval.py --retrieval-mode hyde                    # 切换检索策略
    python scripts/run_eval.py --retrieval-mode hyde --temperature 0    # 固定温度求可复现
    python scripts/run_eval.py --retrieval-mode hyde --temperature 0.7 --runs 5  # 多次跑看波动
    python scripts/run_eval.py --questions path/to/custom.json

指标说明：
    Hit Rate — top_k 结果中至少一个 chunk 命中期望关键词的比例
    MRR      — Mean Reciprocal Rank，第一个命中 chunk 排名的倒数均值

两种评估模式：
    可复现点估计：--temperature 0 --runs 1     （公平 A/B 对比）
    鲁棒性评估：  --temperature 0.7 --runs 5   （报 mean ± std，看真实波动）

前置条件：
    1. Qdrant 正在运行（docker compose up -d qdrant）
    2. 至少已上传一篇文档（状态 READY）
    3. 从项目根目录运行
"""

import argparse
import json
import os
import statistics
import sys
from pathlib import Path

# 绕过本地地址的系统代理：macOS 系统代理（如 Clash）会让 httpx 把发往 localhost 的
# 请求也转发给代理，导致连接 Qdrant 超时。必须在创建任何 httpx 客户端前设置。
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")

# 让脚本能 import app.*（从项目根目录运行时生效）
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.services.retrieval import get_retriever
from app.services.vector_store import get_vector_store

COL_W = 50  # 问题列宽度


def run_single(questions: list[dict], top_k: int, retriever) -> tuple[float, float, list]:
    """跑一轮评估，返回 (hit_rate, mrr, per_question)。纯计算，不打印。"""
    hits = 0
    reciprocal_ranks: list[float] = []
    per_question: list[tuple[str, int | None]] = []

    for item in questions:
        keywords = [kw.lower() for kw in item["expected_keywords"]]
        chunks = retriever.retrieve(item["question"], top_k=top_k)

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
        per_question.append((item["question"], first_hit_rank))

    total = len(questions)
    hit_rate = hits / total if total else 0.0
    mrr = sum(reciprocal_ranks) / total if total else 0.0
    return hit_rate, mrr, per_question


def print_table(per_question: list) -> None:
    print(f"\n{'Question':<{COL_W}} {'Hit':<5} {'Rank'}")
    print("-" * (COL_W + 12))
    for q, rank in per_question:
        marker = "✓" if rank else "✗"
        rank_str = str(rank) if rank else "-"
        disp = q[: COL_W - 2] + ".." if len(q) > COL_W else q
        print(f"{disp:<{COL_W}} {marker:<5} {rank_str}")
    print("-" * (COL_W + 12))


def evaluate(questions, top_k, retrieval_mode, temperature, runs) -> None:
    if settings.embedding_mode == "mock":
        print("WARNING: embedding_mode=mock — 检索结果基于随机哈希，数字无参考价值。")
        print("         请在 .env 中设置 EMBEDDING_MODE=openai 后重新运行。\n")

    # 前置检查：连不上 / 空集合尽早报错
    try:
        chunk_count = get_vector_store(settings).count()
    except Exception as e:
        print(f"ERROR: 无法连接 Qdrant — {e}")
        print("       请先运行：docker compose up -d qdrant")
        sys.exit(1)

    if chunk_count == 0:
        print("ERROR: Qdrant 集合为空，请先上传文档。")
        sys.exit(1)

    mode = retrieval_mode or settings.retrieval_mode
    temp = settings.retrieval_temperature if temperature is None else temperature
    retriever = get_retriever(settings, mode=mode, temperature=temp)

    print(
        f"集合 {chunk_count} chunk | 评估开始"
        f"（mode={mode}, top_k={top_k}, temperature={temp}, runs={runs}）"
    )

    hit_rates: list[float] = []
    mrrs: list[float] = []
    for i in range(runs):
        hit_rate, mrr, per_q = run_single(questions, top_k, retriever)
        hit_rates.append(hit_rate)
        mrrs.append(mrr)
        if runs == 1:
            print_table(per_q)        # 单次跑：打印逐题命中表
        else:
            print(f"  run {i + 1}/{runs}: Hit Rate={hit_rate:.1%}  MRR={mrr:.4f}")

    print()
    if runs == 1:
        print(f"Hit Rate : {hit_rates[0]:.1%}")
        print(f"MRR      : {mrrs[0]:.4f}")
    else:
        # stdev 需要 N≥2；temperature=0 时各轮应几乎一致（std≈0）
        hr_std = statistics.stdev(hit_rates) if runs >= 2 else 0.0
        mrr_std = statistics.stdev(mrrs) if runs >= 2 else 0.0
        print(f"===== 统计 runs={runs}, temperature={temp} =====")
        print(
            f"Hit Rate : mean={statistics.mean(hit_rates):.1%} ± {hr_std:.1%}"
            f"  (min {min(hit_rates):.1%}, max {max(hit_rates):.1%})"
        )
        print(
            f"MRR      : mean={statistics.mean(mrrs):.4f} ± {mrr_std:.4f}"
            f"  (min {min(mrrs):.4f}, max {max(mrrs):.4f})"
        )
    print(f"top_k    : {top_k}")


def main() -> None:
    parser = argparse.ArgumentParser(description="评估 RAG 检索质量（Hit Rate + MRR）")
    parser.add_argument(
        "--questions",
        type=Path,
        default=Path(__file__).parent / "baseline_questions.json",
        help="问题集 JSON（默认：scripts/baseline_questions.json）",
    )
    parser.add_argument("--top-k", type=int, default=3, help="检索返回 chunk 数（默认 3）")
    parser.add_argument(
        "--retrieval-mode",
        type=str,
        default=None,
        help="simple | multi_query | hyde（默认读 settings.retrieval_mode）",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="含 LLM 策略的生成温度（默认读 settings.retrieval_temperature；0=可复现）",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="重复运行次数；>1 时报告 mean±std（默认 1）",
    )
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="开启 LLM 重排（正交叠加在 --retrieval-mode 之上）",
    )
    args = parser.parse_args()

    if args.rerank:
        settings.rerank_enabled = True   # 正交开关：get_retriever 会据此包一层 RerankRetriever

    if not args.questions.exists():
        print(f"ERROR: 找不到问题集文件：{args.questions}")
        sys.exit(1)

    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    print(f"已加载 {len(questions)} 道问题 ← {args.questions}")
    evaluate(questions, args.top_k, args.retrieval_mode, args.temperature, args.runs)


if __name__ == "__main__":
    main()
