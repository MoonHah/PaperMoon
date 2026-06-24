from app.agent.schemas import CitedChunk
from app.core import database
from app.core.config import settings
from app.core.context import get_current_user_id, get_document_scope
from app.repositories import document_repository
from app.services import document_service
from app.services.llm_service import get_llm_service
from app.services.retrieval import get_retriever

# 工具均由 graph_agent.run 在设置好 current_user_id / current_document_scope contextvar 后
# 经 Agent 调用，故这里读 contextvar 即可拿到当前用户 + 对话文档范围，做按用户隔离 + 范围限定。
# SessionLocal 用模块限定 database.SessionLocal()（而非 from ... import）：便于测试统一替换为测试库。


def _load_text_or_guide(db, user_id: str | None, document_id: str) -> str:
    """取正文；失败转成给 LLM 的可操作指引——引导它先 list_documents 拿真实 ID 再重试，
    而不是把裸异常丢回去让它瞎猜（ACI：指导性错误优于裸 str(exception)）。"""
    try:
        return document_service.load_text(db, user_id, document_id)
    except ValueError as e:
        raise ValueError(
            f"未找到 document_id={document_id!r} 对应的文档或其内容不可用（不存在/非本人/未就绪）。"
            "请先调用 list_documents 获取当前可用文档的真实 document_id，再用准确的 ID 重试。"
        ) from e


def search_documents(query: str, top_k: int = 5) -> list[CitedChunk]:
    chunks = get_retriever(settings).retrieve(
        query,
        top_k=top_k,
        user_id=get_current_user_id(),
        document_ids=get_document_scope(),   # 用户勾选范围；None=全部已就绪文档
    )
    return [CitedChunk(**chunk) for chunk in chunks]


def list_documents() -> list[dict]:
    """列出当前用户已就绪（READY）的文档，供 agent 把自然语言指代映射到真实 document_id。

    若本轮对话限定了文档范围（用户勾选），只列范围内的，避免 agent 漫游到范围外文档。
    """
    user_id = get_current_user_id()
    if user_id is None:
        return []
    scope = get_document_scope()
    db = database.SessionLocal()
    try:
        docs = document_repository.get_all_by_user(db, user_id)
        return [
            {"document_id": d.document_id, "filename": d.filename}
            for d in docs
            if d.status == "READY" and (scope is None or d.document_id in scope)
        ]
    finally:
        db.close()


def summarize_document(document_id: str) -> str:
    db = database.SessionLocal()
    try:
        content = _load_text_or_guide(db, get_current_user_id(), document_id)
    finally:
        db.close()

    # 截断到字符预算：大文档整篇塞进单次调用会超时（与笔记同源风险），共用 truncate_for_llm。
    llm = get_llm_service(settings)
    return llm.chat(
        "请为这篇文档生成一份简洁但包含核心重点内容的总结, 同时确保不伪造数据或者文章内容。",
        context_chunks=[document_service.truncate_for_llm(content)],
    )


def compare_documents(document_ids: list[str]) -> str:
    # 入参护栏：去重（保序）后须有 ≥2 篇不同文档，否则给可操作指引而非笼统报错。
    ids = list(dict.fromkeys(document_ids))
    if len(ids) < 2:
        raise ValueError(
            "对比至少需要 2 篇不同的文档。请先调用 list_documents 选出 ≥2 个不同的 document_id 再重试。"
        )

    user_id = get_current_user_id()
    db = database.SessionLocal()
    try:
        contents = [_load_text_or_guide(db, user_id, doc_id) for doc_id in ids]
    finally:
        db.close()

    # 每篇各自截断到字符预算：多篇正文累加更易爆上下文/超时，逐篇 truncate_for_llm。
    contents = [document_service.truncate_for_llm(c) for c in contents]
    llm = get_llm_service(settings)
    return llm.chat(
        query=(
            "请对以上文档进行结构化对比分析，按以下维度输出：\n"
            "1. 核心主题：每篇文档的核心主题是什么\n"
            "2. 主要论点：各自的核心观点或结论\n"
            "3. 异同点：这些文档在内容、方法或结论上的主要相似和差异\n"
            "4. 综合评价：综合来看哪篇更深入或更实用，理由是什么\n"
            "只基于提供的文档内容作答，不要补充文档中没有的信息。"
        ),
        context_chunks=contents,
    )


def generate_markdown_notes(topic: str, query: str) -> str:
    # 注意区分两套"笔记"（非冗余，入口不同）：
    #   - 本工具：对话内「按需」围绕 topic 检索片段即时生成，是 agent 的一个 tool。
    #   - document_service.run_notes_generation：文档级「预生成」整篇笔记，异步落盘，走 /documents/{id}/notes。
    chunks = search_documents(query)
    contents = [chunk.text for chunk in chunks]
    llm = get_llm_service(settings)
    result = llm.chat(
        query=(
            f"请基于以上内容，生成一份关于「{topic}」的结构化 Markdown 学习笔记。\n"
            "要求：\n"
            "1. 用 ## 分隔主要章节\n"
            "2. 包含核心概念解释、关键要点和示例\n"
            "3. 结尾附一个「总结」章节\n"
            "只使用文档中提供的内容，不要补充额外信息。"
        ),
        context_chunks=contents,
    )

    return result