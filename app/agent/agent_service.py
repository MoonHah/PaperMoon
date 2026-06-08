from app.agent import tools
from app.agent.schemas import AgentRunRequest, AgentRunResponse, CitedChunk, IntermediateStep

_RULES = [
    (["总结", "概括", "摘要", "summarize"], "summarize_document"),
    (["对比", "比较", "区别", "不同", "compare"], "compare_documents"),
    (["笔记", "学习笔记", "整理", "notes"], "generate_markdown_notes"),
]


def select_tool(query: str, document_ids: list[str]) -> tuple[str, str]:
    """返回 (工具名, 选择原因)"""
    for keywords, tool in _RULES:
        if any(kw in query for kw in keywords):
            if tool == "summarize_document" and not document_ids:
                return "search_documents", "关键词匹配'总结'但未提供 document_id, 降级为搜索"
            if tool == "compare_documents" and len(document_ids) < 2:
                return "search_documents", "关键词匹配'对比'但 document_id 不足 2 个, 降级为搜索"
            matched = [kw for kw in keywords if kw in query]
            return tool, f"关键词匹配: {matched}"
    return "search_documents", "无关键词匹配，使用默认搜索"


def run(request: AgentRunRequest) -> AgentRunResponse:
    steps = []

    # Step 1: 选择工具
    tool_name, reason = select_tool(request.user_query, request.document_ids)
    steps.append(IntermediateStep(
        step=1, action="tool_selection", detail=reason, status="ok"
    ))

    # Step 2: 执行工具
    final_answer: str
    citations: list[CitedChunk] = []

    try:
        if tool_name == "search_documents":
            chunks = tools.search_documents(request.user_query)
            citations = chunks
            final_answer = "\n\n---\n\n".join(c.text for c in chunks) if chunks else "未找到相关内容。"

        elif tool_name == "summarize_document":
            final_answer = tools.summarize_document(request.document_ids[0])

        elif tool_name == "compare_documents":
            final_answer = tools.compare_documents(request.document_ids)

        elif tool_name == "generate_markdown_notes":
            final_answer = tools.generate_markdown_notes(
                topic=request.user_query,
                query=request.user_query,
            )

        else:
            raise ValueError(f"未知工具: {tool_name}")

        steps.append(IntermediateStep(
            step=2, action="tool_execution", detail=f"工具 {tool_name} 执行成功", status="ok"
        ))

    except Exception as e:
        steps.append(IntermediateStep(
            step=2, action="tool_execution", detail=str(e), status="error"
        ))
        return AgentRunResponse(
            final_answer="工具执行失败，请检查输入参数。",
            selected_tool=tool_name,
            intermediate_steps=steps,
            error=str(e),
        )

    # Step 3: 组装返回
    return AgentRunResponse(
        final_answer=final_answer,
        selected_tool=tool_name,
        intermediate_steps=steps,
        citations=citations,
    )
