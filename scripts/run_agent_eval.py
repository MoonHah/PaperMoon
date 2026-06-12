"""
Agent 工具选择评估：验证 LLM function calling 给定 query 是否选对工具。

用法：
    python scripts/run_agent_eval.py

只依赖 LLM（不需要 Qdrant/DB）——隔离评估「工具选择」这一 agent 质量的第一道关。
需要 LLM_MODE=openai 才有意义（mock 用关键词近似，非真实 LLM 能力）。

指标：
    Tool Selection Accuracy — 给定问题，agent 选对工具的比例。
"""

import os
import sys
from pathlib import Path

# 绕过本地地址的系统代理（与 run_eval 一致）；本脚本只调 OpenAI，但保持一致无害。
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agent.tool_schemas import TOOL_SCHEMAS
from app.core.config import settings
from app.services.llm_service import get_llm_service

# 每条用例：自然语言问题 + 期望选中的工具。覆盖 4 个工具 + 同义/口语化表述。
CASES = [
    {"query": "这篇论文的核心贡献是什么？", "expected": "search_documents"},
    {"query": "Agent Skills 有哪些安全风险？", "expected": "search_documents"},
    {"query": "26.1% 这个数字是怎么来的？", "expected": "search_documents"},
    {"query": "帮我总结一下这篇文档的主要内容", "expected": "summarize_document"},
    {"query": "给这篇文档写一个整体概览", "expected": "summarize_document"},
    {"query": "对比这两篇论文在方法上的差异", "expected": "compare_documents"},
    {"query": "比较一下这几篇文章的结论有什么不同", "expected": "compare_documents"},
    {"query": "整理一份关于 RAG 评估的学习笔记", "expected": "generate_markdown_notes"},
    {"query": "帮我做一份 markdown 格式的学习笔记", "expected": "generate_markdown_notes"},
]


def main() -> None:
    if settings.llm_mode == "mock":
        print("WARNING: llm_mode=mock — 工具选择基于关键词近似，非真实 LLM。请设 LLM_MODE=openai。\n")

    svc = get_llm_service(settings)
    correct = 0

    for c in CASES:
        result = svc.choose_tool(c["query"], TOOL_SCHEMAS)
        got = result[0] if result else "(none)"
        ok = got == c["expected"]
        correct += ok
        print(f"{'✓' if ok else '✗'} {c['query']}")
        print(f"    expected={c['expected']}  got={got}")

    total = len(CASES)
    print("-" * 60)
    print(f"Tool Selection Accuracy: {correct}/{total} = {correct / total:.1%}")


if __name__ == "__main__":
    main()
