"""Agent 工具定义：@tool 包装 + 系统提示。

@tool 的 docstring 即「给 LLM 的工具说明书」（= schema 的 description）；包装层只把调用转交
app.agent.tools 的实现，并用 content_and_artifact 把结构化引用透出供 runner 回收。
与图构建(graph_build)、运行服务(graph_agent)解耦，便于单独维护工具契约。
"""

from langchain_core.messages import SystemMessage
from langchain_core.tools import tool

from app.agent import tools as _impl    # 复用现有工具实现


# 系统提示：每次调用前临时注入（不写入 state，故不进 checkpointer 历史）。
# document_id 仅供 Agent 内部调工具用，不要回显给用户——用户看到 UUID 体验很差。
_SYSTEM_PROMPT = SystemMessage(
    content=(
        "你是 PaperMoon 的文档阅读助手，同时也是用户的通用助手。回答遵循以下来源与标注规则：\n"
        "1. 优先依据检索到的文档内容作答，并用文件名指代文档；"
        "绝不向用户展示 document_id / UUID（它们仅供你内部调用工具使用）。\n"
        "2. 当检索结果为空或与问题无关时，先明确告知用户「文档库中没有与该问题相关的内容」，"
        "随后可基于你自己的通用知识作答，但必须显式标注「以下为通用知识，非来自你的文档」。\n"
        "3. 文档能回答的部分严格基于文档；文档未覆盖的部分才用通用知识（并标注）。"
        "绝不把通用知识伪装成来自文档的内容，也不得编造文档里没有的细节。"
    )
)


# ── 工具：@tool 的 docstring 即「给 LLM 的工具说明书」（= schema 的 description）──

@tool(response_format="content_and_artifact")
def search_documents(query: str) -> tuple[str, list[dict]]:
    """在文档库中检索与问题最相关的片段，回答关于文档内容的具体问题。当用户提问但没有明确要求总结/对比/做笔记时，默认使用这个。

    Args:
        query: 用于检索的查询文本。
    """
    # content_and_artifact：返回 (给 LLM 看的字符串, 结构化引用)。
    # 字符串进 ToolMessage.content（LLM 行为不变），结构化引用进 ToolMessage.artifact，
    # 供 run() 跑完回收成 citations——绕开「ToolNode 把结果压成字符串丢失结构」的问题。
    chunks = _impl.search_documents(query)
    content = "\n\n---\n\n".join(c.text for c in chunks) if chunks else "未找到相关内容。"
    artifact = [c.model_dump() for c in chunks]
    return content, artifact


@tool
def list_documents() -> str:
    """列出当前文档库中所有可用文档的文件名和 document_id。当用户用自然语言指代文档（如「那两篇」「关于 X 的论文」）、需要先确定具体是哪些文档时，先调它拿到真实 document_id，再调用 summarize_document / compare_documents。"""
    docs = _impl.list_documents()
    if not docs:
        return "文档库为空。"
    return "当前可用文档：\n" + "\n".join(
        f"- {d['filename']} (document_id: {d['document_id']})" for d in docs
    )


@tool
def summarize_document(document_id: str) -> str:
    """对单独一篇完整文档（由 document_id 指定）生成整体总结/概览。仅当只针对一篇文档、且不涉及与其他文档比较时使用；若用户要对比多篇文档，应改用 compare_documents。

    Args:
        document_id: 要总结的文档 ID（可先用 list_documents 获取真实 ID）。
    """
    return _impl.summarize_document(document_id)


@tool
def compare_documents(document_ids: list[str]) -> str:
    """对比两篇或多篇文档在内容、方法或结论上的异同。只要用户提到「对比」「比较」「差异」「异同」「不同」且涉及多篇文档就用它——即使问的是「方法上的差异」「结论的不同」也属于对比，不要误选 summarize_document。

    Args:
        document_ids: 要对比的文档 ID 列表，至少 2 个（可先用 list_documents 获取真实 ID）。
    """
    return _impl.compare_documents(document_ids)


@tool
def generate_markdown_notes(topic: str, query: str) -> str:
    """围绕某个主题、基于文档内容生成结构化的 Markdown 学习笔记。用户要求整理笔记时用。

    Args:
        topic: 学习笔记的主题。
        query: 用于检索相关内容的查询文本。
    """
    return _impl.generate_markdown_notes(topic, query)


# 汇总列表（绑定 LLM + 构建 ToolNode 都用它）——必须放在所有 @tool 定义之后
TOOLS = [
    search_documents,
    list_documents,
    summarize_document,
    compare_documents,
    generate_markdown_notes,
]
