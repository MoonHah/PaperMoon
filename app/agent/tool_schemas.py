TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "在已上传的文档库中检索与问题最相关的片段，用于回答关于文档内容的具体问题。当用户提问但没有明确要求总结/对比/做笔记时，默认用这个。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "用于检索的查询文本",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_document",
            "description": "对单独一篇完整文档（由 document_id 指定）生成整体总结/概览。仅当只针对一篇文档、且不涉及与其他文档比较时使用；若用户要对比多篇文档，应改用 compare_documents，而不是本工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "要总结的文档 ID",
                    },
                },
                "required": ["document_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_documents",
            "description": "对比两篇或多篇文档在内容、方法或结论上的异同。只要用户提到「对比」「比较」「差异」「异同」「不同」且涉及多篇文档就用它——即使问的是「方法上的差异」「结论的不同」也属于对比，不要误选 summarize_document。",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要对比的文档 ID 列表，至少 2 个",
                    },
                },
                "required": ["document_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_markdown_notes",
            "description": "围绕某个主题、基于文档内容生成结构化的 Markdown 学习笔记。用户要求整理笔记时用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "学习笔记的主题",
                    },
                    "query": {
                        "type": "string",
                        "description": "用于检索相关内容的查询文本",
                    },
                },
                "required": ["topic", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_documents",
            "description": "列出当前文档库中所有可用文档的文件名和 document_id。当用户用自然语言指代文档（如「那两篇」「关于 X 的论文」）、需要先确定具体是哪些文档时，先调用它拿到真实 document_id，再调用 summarize_document / compare_documents。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
