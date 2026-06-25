"""
Agent 端到端答案质量评估（LLM-as-judge）

让 golden 问题逐题过真实 agent（graph_agent.run），再用一个 judge LLM 给答案打分。
覆盖 run_eval.py 测不到的「最终答案质量」与「hybrid grounding 行为」：
  - 库内问题：答案是否严格基于检索来源、不幻觉（groundedness）+ 是否切题（relevance）
  - 库外问题：是否正确「说明文档库无相关内容 + 标注通用知识」（correct_out_of_corpus）

用法：
    python scripts/run_agent_eval.py --user-id <USER_ID>
    python scripts/run_agent_eval.py --user-id <USER_ID> --questions path/to/custom.json

前置条件：
    1. LLM_MODE=openai 且 EMBEDDING_MODE=openai（mock 无评估意义）
    2. Qdrant / Postgres 在运行，且该 user 的文档已索引（READY）
    3. 从项目根目录运行
    judge 用同一 LLM（temperature=0 求可复现）；会产生少量 OpenAI 调用成本。
"""

import argparse
import json
import os
import sys
from pathlib import Path

# 绕过本地地址的系统代理（与 run_eval 一致），否则发往 localhost 的 Qdrant/PG 请求会被系统代理劫持。
os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agent import graph_agent
from app.agent.schemas import AgentRunRequest
from app.core.config import settings
from app.core.database import SessionLocal
from app.repositories import user_repository
from app.services.llm_service import get_llm_service
from app.services.vector_store import get_vector_store

COL_W = 46

_JUDGE_PROMPT = """你是严格的答案质量评审。根据[问题]、[助手答案]、[检索到的来源]、[问题类型]评分。
只输出一个 JSON 对象，不要任何解释或多余文字，格式：
{{"groundedness": <1-5整数>, "relevance": <1-5整数>, "correct_behavior": <true|false|null>}}

评分维度：
- groundedness：答案是否严格基于[来源]、无编造。来源为空时此项填 3（不适用）。
- relevance：答案是否切题、回应了问题。
- correct_behavior：按[问题类型]判定该轮行为是否符合预期——
    in_corpus（库内）：填 null（由 groundedness/relevance 衡量即可）。
    out_of_corpus（库外知识型，如「什么是 X」）：正确 = 明确说明「文档库中没有相关内容」，
      并把后续内容标注为通用知识。
    general_task（通用任务型，如「写一段代码」）：正确 = 作为通用助手完成任务，
      且标注这是通用知识/非来自文档（不要求出现「文档库无相关」字样）。

[问题类型] {qtype}

[问题]
{question}

[助手答案]
{answer}

[检索到的来源]
{sources}
"""


def _judge(question: str, answer: str, sources: str, qtype: str) -> dict | None:
    """调 judge LLM 给一条答案打分，解析 JSON；失败返回 None（标记未评分）。"""
    prompt = _JUDGE_PROMPT.format(question=question, answer=answer, sources=sources, qtype=qtype)
    raw = get_llm_service(settings).complete(prompt, temperature=0.0).strip()
    # 容错：剥可能的 ```json 围栏，截取首个 { 到末个 }
    if "{" in raw and "}" in raw:
        raw = raw[raw.index("{") : raw.rindex("}") + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def evaluate(questions: list[dict], user_id: str) -> None:
    if settings.llm_mode == "mock" or settings.embedding_mode == "mock":
        print("WARNING: llm_mode/embedding_mode=mock — 答案与检索非真实，评估无意义。")
        print("         请设 LLM_MODE=openai 且 EMBEDDING_MODE=openai 后重跑。\n")

    try:
        n_chunks = get_vector_store(settings).count(user_id=user_id)
    except Exception as e:
        print(f"ERROR: 无法连接 Qdrant — {e}\n       请先 docker compose up -d qdrant")
        sys.exit(1)
    if n_chunks == 0:
        print(f"ERROR: user {user_id} 在向量库中没有任何 chunk，请先用该账号上传并索引文档。")
        sys.exit(1)

    print(f"user={user_id} | 该用户 {n_chunks} chunk | 跑 {len(questions)} 题\n")

    rows: list[tuple[str, str, dict | None]] = []
    for item in questions:
        q, qtype = item["question"], item.get("type", "in_corpus")
        resp = graph_agent.run(AgentRunRequest(user_query=q), user_id)
        sources = "\n\n".join(c.text for c in resp.citations) if resp.citations else "（无检索来源）"
        score = _judge(q, resp.final_answer, sources, qtype)
        rows.append((q, qtype, score))
        mark = "?" if score is None else "ok"
        print(f"[{mark}] ({qtype}) {q}\n    {score}")

    _summarize(rows)


def _summarize(rows: list[tuple[str, str, dict | None]]) -> None:
    def _vals(key: str, qtype_filter=None) -> list:
        return [
            s[key]
            for q, t, s in rows
            if s is not None and key in s and s[key] is not None
            and (qtype_filter is None or t == qtype_filter)
        ]

    ground = _vals("groundedness", "in_corpus")
    rel = _vals("relevance")
    # 库外知识型 + 通用任务型：均由 correct_behavior 衡量「行为是否符合该类型预期」
    behavior = [s["correct_behavior"] for q, t, s in rows
                if s is not None and s.get("correct_behavior") is not None]

    print("\n" + "-" * (COL_W + 12))
    print(f"已评分 {sum(1 for _, _, s in rows if s is not None)}/{len(rows)} 题")
    if ground:
        print(f"Groundedness (库内)      : mean={sum(ground) / len(ground):.2f} / 5")
    if rel:
        print(f"Relevance (全部)         : mean={sum(rel) / len(rel):.2f} / 5")
    if behavior:
        print(f"行为正确率 (库外+任务)   : {sum(behavior)}/{len(behavior)} = {sum(behavior) / len(behavior):.1%}")
    print("-" * (COL_W + 12))


def _resolve_user_id(user_id: str | None, email: str | None) -> str:
    """优先用 --user-id；否则用 --email 查 DB 解析。两者都缺或查不到则报错退出。"""
    if user_id:
        return user_id
    if email:
        db = SessionLocal()
        try:
            user = user_repository.get_by_email(db, email.strip().lower())
        finally:
            db.close()
        if user is None:
            print(f"ERROR: 找不到邮箱为 {email} 的用户。")
            sys.exit(1)
        return user.id
    print("ERROR: 请提供 --user-id 或 --email 之一。")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent 端到端答案质量评估（LLM-as-judge）")
    parser.add_argument("--user-id", help="评估对象用户 id（其文档须已索引）")
    parser.add_argument("--email", help="用邮箱代替 --user-id（从 DB 解析；二选一）")
    parser.add_argument(
        "--questions",
        type=Path,
        default=Path(__file__).parent / "agent_eval_questions.json",
        help="问题集 JSON（默认：scripts/agent_eval_questions.json）",
    )
    args = parser.parse_args()

    if not args.questions.exists():
        print(f"ERROR: 找不到问题集文件：{args.questions}")
        sys.exit(1)

    user_id = _resolve_user_id(args.user_id, args.email)
    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    print(f"已加载 {len(questions)} 道问题 ← {args.questions}")
    evaluate(questions, user_id)


if __name__ == "__main__":
    main()
