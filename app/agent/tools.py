from app.agent.schemas import CitedChunk
from app.core.config import settings
from app.core.database import SessionLocal
from app.repositories import document_repository
from app.services import document_service
from app.services.llm_service import get_llm_service
from app.services.retrieval import get_retriever


def search_documents(query: str, top_k: int = 5) -> list[CitedChunk]:
    chunks = get_retriever(settings).retrieve(query, top_k=top_k)
    return [CitedChunk(**chunk) for chunk in chunks]


def list_documents() -> list[dict]:
    """列出库中所有已就绪（READY）的文档，供 agent 把用户的自然语言指代映射到真实 document_id。"""
    db = SessionLocal()
    try:
        docs = document_repository.get_all(db)
        return [
            {"document_id": d.document_id, "filename": d.filename}
            for d in docs
            if d.status == "READY"
        ]
    finally:
        db.close()


def summarize_document(document_id: str) -> str:
    db = SessionLocal()
    try:
        content = document_service.load_text(db, document_id)
    finally:
        db.close()

    llm = get_llm_service(settings)
    return llm.chat(
        "请为这篇文档生成一份简洁但包含核心重点内容的总结, 同时确保不伪造数据或者文章内容。",
        context_chunks=[content],
    )


def compare_documents(document_ids: list[str]) -> str:
    if len(document_ids) < 2:
        raise ValueError("Compare needs at least 2 documents!")

    db = SessionLocal()
    try:
        contents = [document_service.load_text(db, doc_id) for doc_id in document_ids]
    finally:
        db.close()

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