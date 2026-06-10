from typing import Protocol


class Retriever(Protocol):
    """检索策略的统一抽象。

    给一个自然语言 query，返回最相关的 chunk 列表（按相关性排序，最多 top_k 条）。
    每个元素是一个 dict，包含以下键：
        - text:        chunk 文本内容
        - document_id: 来源文档 ID
        - filename:    来源文件名
    具体检索方式（直连向量库、Multi Query…）由实现类决定，调用方只依赖本契约。
    """

    def retrieve(self, query: str, top_k: int) -> list[dict]: ...