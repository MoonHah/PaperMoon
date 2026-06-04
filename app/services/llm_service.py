from typing import Protocol 


class LLMClient(Protocol):
    def chat(self, query: str, context_chunks: list[str]) -> str: ...


class MockLLMService:
    def chat(self, query: str, context_chunks: list[str]) -> str:
        if not context_chunks:
            return "[MOCK] No relevant context found."
        context = "\n\n---\n\n".join(
            f"[Chunk {i+1}]\n{chunk}"
            for i, chunk in enumerate(context_chunks)
        )
        return f"[MOCK] Query: {query}\n\nRetrieved context:\n\n{context}"
        

class OpenAILLMService:
    def __init__(self, api_key: str, base_url: str, model: str):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
    
    def chat(self, query: str, context_chunks: list[str]) -> str:
        context = "\n\n---\n\n".join(context_chunks)
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个基于文档回答问题的助手，只根据提供的上下文回答，如果上下文中没有答案请明确说明。"},
                {"role": "user", "content": f"上下文：\n{context}\n\n问题: {query}"},
            ],
            timeout=30.0,
        )
        answer = resp.choices[0].message.content
        return answer or ""


def get_llm_service(settings) -> LLMClient:
    if settings.llm_mode == "mock":
        return MockLLMService()
    return OpenAILLMService(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.llm_model,
    )