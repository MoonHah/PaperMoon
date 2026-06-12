import json

from app.agent import tools
from app.agent.schemas import AgentRunRequest, AgentRunResponse, CitedChunk, IntermediateStep
from app.agent.tool_schemas import TOOL_SCHEMAS
from app.core.config import settings
from app.services.llm_service import get_llm_service

MAX_STEPS = 5   # 兜底防死循环


def _execute_tool(name: str, args: dict, request: AgentRunRequest) -> tuple[str, list[CitedChunk]]:
    """执行单个工具，返回 (字符串结果, citations)。

    结果必须是字符串（要作为 tool message 的 content 回填）；只有 search 产生 citations。
    工具失败时返回错误字符串（而非抛异常），让 LLM 能「看到」失败、有机会换策略。
    """
    try:
        if name == "list_documents":
            docs = tools.list_documents()
            if not docs:
                return "文档库为空。", []
            listing = "\n".join(f"- {d['filename']} (document_id: {d['document_id']})" for d in docs)
            return f"当前可用文档：\n{listing}", []

        elif name == "search_documents":
            chunks = tools.search_documents(args.get("query", request.user_query))
            text = "\n\n---\n\n".join(c.text for c in chunks) if chunks else "未找到相关内容。"
            return text, chunks

        elif name == "summarize_document":
            doc_id = request.document_ids[0] if request.document_ids else args.get("document_id")
            if not doc_id:
                return "错误：未指定 document_id，请先调用 list_documents 查看可用文档。", []
            return tools.summarize_document(doc_id), []

        elif name == "compare_documents":
            doc_ids = request.document_ids or args.get("document_ids", [])
            if len(doc_ids) < 2:
                return "错误：对比需要至少 2 个 document_id，请先调用 list_documents 查看可用文档。", []
            return tools.compare_documents(doc_ids), []

        elif name == "generate_markdown_notes":
            return tools.generate_markdown_notes(
                topic=args.get("topic", request.user_query),
                query=args.get("query", request.user_query),
            ), []

        return f"未知工具: {name}", []
    except Exception as e:
        # 工具执行失败 → 返回错误字符串（不抛），让 LLM 下一轮「看到」失败、有机会换策略
        return f"工具 {name} 执行失败：{e}", []


def run(request: AgentRunRequest) -> AgentRunResponse:
    messages: list[dict] = [{"role": "user", "content": request.user_query}]
    steps: list[IntermediateStep] = []
    citations: list[CitedChunk] = []
    llm = get_llm_service(settings)

    try:
        for _ in range(MAX_STEPS):
            assistant = llm.agent_step(messages, TOOL_SCHEMAS)
            messages.append(assistant)                  # 关键①：assistant 消息回填历史

            tool_calls = assistant.get("tool_calls")
            if not tool_calls:                          # 终止：无工具调用 = 给了最终答案
                return AgentRunResponse(
                    final_answer=assistant.get("content") or "",
                    selected_tool="(final)",
                    intermediate_steps=steps,
                    citations=citations,
                )

            for tc in tool_calls:                       # 执行每个工具，结果回填（注意：在主循环内！）
                name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])
                result, cites = _execute_tool(name, args, request)
                citations.extend(cites)
                steps.append(IntermediateStep(
                    step=len(steps) + 1, action=name, detail=str(args), status="ok",
                ))
                messages.append({                       # 关键②：tool 结果回填（带 tool_call_id）
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

        # 跑满 MAX_STEPS 仍未收尾 → 兜底
        return AgentRunResponse(
            final_answer="达到最大推理步数，请简化问题后重试。",
            selected_tool="(max_steps)",
            intermediate_steps=steps,
            citations=citations,
        )

    except Exception as e:
        return AgentRunResponse(
            final_answer="Agent 执行失败，请稍后重试。",
            selected_tool="(error)",
            intermediate_steps=steps,
            error=str(e),
        )
