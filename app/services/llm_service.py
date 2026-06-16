import json
import logging
from collections.abc import Iterator
from typing import Any, Protocol

import httpx
import openai
from openai.types.chat import ChatCompletionMessageParam

from app.services._openai_retry import openai_retry

logger = logging.getLogger(__name__)

# RAG 问答的 system 约束：只依据上下文作答，防止模型凭记忆编造。
_RAG_SYSTEM_PROMPT = (
    "你是一个基于文档回答问题的助手，只根据提供的上下文回答，如果上下文中没有答案请明确说明。"
)


class LLMClient(Protocol):
    """LLM 客户端契约。

    chat / stream_chat 面向 RAG 问答（自带上下文约束）；
    complete 是不带任何框架的通用文本生成，供查询改写、HyDE 等场景使用。
    complete 的 temperature 默认 0.0 求可复现；调用方可显式调高以获取多样性。
    """

    def chat(self, query: str, context_chunks: list[str]) -> str: ...
    def stream_chat(self, query: str, context_chunks: list[str]) -> Iterator[str]: ...
    def complete(self, prompt: str, temperature: float = 0.0) -> str: ...
    def choose_tool(self, query: str, tools: list[dict]) -> tuple[str, dict] | None: ...
    def agent_step(self, messages: list[dict], tools: list[dict]) -> dict: ...


class MockLLMService:
    def chat(self, query: str, context_chunks: list[str]) -> str:
        if not context_chunks:
            return "[MOCK] No relevant context found."
        context = "\n\n---\n\n".join(
            f"[Chunk {i+1}]\n{chunk}"
            for i, chunk in enumerate(context_chunks)
        )
        return f"[MOCK] Query: {query}\n\nRetrieved context:\n\n{context}"

    def stream_chat(self, query: str, context_chunks: list[str]) -> Iterator[str]:
        full = self.chat(query, context_chunks)
        for word in full.split(" "):
            yield word + " "

    def complete(self, prompt: str, temperature: float = 0.0) -> str:
        # mock 不做真实生成，返回空串 —— 让上层（HyDE / MultiQuery）自动降级
        # temperature 对 mock 无意义，仅为接口一致保留
        return ""

    def choose_tool(self, query, tools):
        # mock 用简单关键词模拟 LLM 的工具选择，给测试一个可预测的替身，
        # 以便在没有真实 LLM 的情况下验证 agent 的调度逻辑。
        if any(k in query for k in ("总结", "概括", "summarize")):
            return ("summarize_document", {})
        if any(k in query for k in ("对比", "比较", "compare")):
            return ("compare_documents", {})
        if any(k in query for k in ("笔记", "notes")):
            return ("generate_markdown_notes", {"topic": query, "query": query})
        return ("search_documents", {"query": query})
    
    def agent_step(self, messages: list[dict], tools: list[dict]) -> dict:
        # mock 模拟两步 ReAct loop：已有工具结果就给最终答案，否则第一步按关键词选工具
        if messages and messages[-1].get("role") == "tool":
            return {"role": "assistant", "content": "[MOCK] answer based on tool results", "tool_calls": None}

        query = next((m["content"] for m in messages if m.get("role") == "user"), "")
        name, args = self.choose_tool(query, tools) or ("search_documents", {"query": query})
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_mock_1",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args)},
                }
            ],
        }



class OpenAILLMService:
    def __init__(self, api_key: str, base_url: str, model: str, timeout: float, max_retries: int):
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries

    def _create(
        self, messages: list[ChatCompletionMessageParam], temperature: float | None = None
    ) -> str:
        """所有非流式调用的统一出口：重试、超时、计费日志只写一遍。

        chat / complete 只负责组装 messages，"怎么调用"的细节收敛在这里。
        temperature 为 None 时沿用 OpenAI 默认（保持 chat 原有行为）；
        显式传入时透传给 API（complete 用它求可复现）。
        """

        @openai_retry(self._max_retries, logger)
        def _call() -> str:
            kwargs: dict[str, Any] = {
                "model": self._model,
                "messages": messages,
                "timeout": self._timeout,
            }
            if temperature is not None:
                kwargs["temperature"] = temperature
            resp = self._client.chat.completions.create(**kwargs)
            if resp.usage:
                logger.info(
                    "llm.token_usage",
                    extra={
                        "model": self._model,
                        "prompt_tokens": resp.usage.prompt_tokens,
                        "completion_tokens": resp.usage.completion_tokens,
                        "total_tokens": resp.usage.total_tokens,
                    },
                )
            return resp.choices[0].message.content or ""

        return _call()


    def chat(self, query: str, context_chunks: list[str]) -> str:
        # RAG 问答：system 约束「只依据上下文」+ user 携带检索到的上下文
        context = "\n\n---\n\n".join(context_chunks)
        return self._create(
            [
                {"role": "system", "content": _RAG_SYSTEM_PROMPT},
                {"role": "user", "content": f"上下文：\n{context}\n\n问题: {query}"},
            ]
        )


    def stream_chat(self, query: str, context_chunks: list[str]) -> Iterator[str]:
        # 流式逐 token yield，与 _create 的一次性返回结构不同，单独保留。
        # 刻意不走 openai_retry：流式中途无法安全重放已发出的 token；瞬时故障由
        # ResilientLLMService 在首 token 处捕获并整体切到 fallback（mock），而非这里重试。
        context = "\n\n---\n\n".join(context_chunks)
        stream = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _RAG_SYSTEM_PROMPT},
                {"role": "user", "content": f"上下文：\n{context}\n\n问题: {query}"},
            ],
            timeout=self._timeout,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def complete(self, prompt: str, temperature: float = 0.0) -> str:
        # 通用文本生成：单条 user message，不套任何 RAG system prompt
        return self._create([{"role": "user", "content": prompt}], temperature=temperature)

    def choose_tool(self, query: str, tools: list[dict]) -> tuple[str, dict] | None:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": query}],
            tools=tools,  # type: ignore[arg-type]  # dict 形式 schema 运行时合法，SDK 的 TypedDict 注解过严
            tool_choice="required",   # agent 必须经工具访问文档，强制选一个（而非 auto 让模型偷懒直接答）
            timeout=self._timeout,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:          # 模型没选工具
            return None
        call = msg.tool_calls[0]        # 单步: 取第一个 tool_call
        if call.type != "function":     # 新版 SDK 的 tool_call 是 union，只处理 function（本项目未定义 custom tools）
            return None
        return call.function.name, json.loads(call.function.arguments)

    def agent_step(self, messages: list[dict], tools: list[dict]) -> dict:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=messages,          # type: ignore[arg-type]
            tools=tools,                # type: ignore[arg-type]
            tool_choice="auto",         # <- loop 要能终止, 必须 auto
            timeout=self._timeout,
        )
        return resp.choices[0].message.model_dump()     # SDK 对象 -> 通用 dict
    


class RemoteLLMService:
    """Calls model-service /generate over HTTP. Forwards X-Request-ID for log correlation."""

    def __init__(self, base_url: str, timeout: float):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def _generate(self, messages: list[dict], temperature: float | None = None) -> str:
        """非流式 /generate 的统一出口：URL、请求头、错误检查只写一遍。"""
        from app.core.logging import get_request_id

        payload: dict[str, Any] = {"messages": messages}
        if temperature is not None:
            payload["temperature"] = temperature
        resp = self._client.post(
            f"{self._base_url}/generate",
            json=payload,
            headers={"X-Request-ID": get_request_id()},
        )
        resp.raise_for_status()
        return resp.json()["content"]

    def chat(self, query: str, context_chunks: list[str]) -> str:
        context = "\n\n---\n\n".join(context_chunks)
        return self._generate(
            [
                {"role": "system", "content": _RAG_SYSTEM_PROMPT},
                {"role": "user", "content": f"上下文：\n{context}\n\n问题: {query}"},
            ]
        )

    def stream_chat(self, query: str, context_chunks: list[str]) -> Iterator[str]:
        from app.core.logging import get_request_id

        context = "\n\n---\n\n".join(context_chunks)
        with self._client.stream(
            "POST",
            f"{self._base_url}/generate/stream",
            json={
                "messages": [
                    {"role": "system", "content": _RAG_SYSTEM_PROMPT},
                    {"role": "user", "content": f"上下文：\n{context}\n\n问题: {query}"},
                ]
            },
            headers={"X-Request-ID": get_request_id()},
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[len("data: "):]
                if data == "[DONE]":
                    break
                payload = json.loads(data)
                if "error" in payload:
                    raise RuntimeError(f"model-service stream error: {payload['error']}")
                yield payload["token"]

    def complete(self, prompt: str, temperature: float = 0.0) -> str:
        # 通用文本生成：单条 user message，不套 RAG system prompt
        return self._generate([{"role": "user", "content": prompt}], temperature=temperature)

    def choose_tool(self, query: str, tools: list[dict]) -> tuple[str, dict]| None:
        # model-service 暂不支持 function calling；Resilient 会自动降级到 fallback（13 后续处理）
        raise NotImplementedError("remote backend does not support function calling yet")
    
    def agent_step(self, messages: list[dict], tools: list[dict]) -> dict:
        # model-service 暂不支持 function calling；Resilient 会自动降级到 fallback（13 后续处理）
        raise NotImplementedError("remote backend does not support agent_step yet")


class ResilientLLMService:
    """包装「主 client + 兜底 client」：主调用抛任何异常都降级到兜底，保证不向上抛错。"""

    def __init__(self, primary: LLMClient, fallback: LLMClient):
        self._primary = primary
        self._fallback = fallback

    def chat(self, query: str, context_chunks: list[str]) -> str:
        from app.core.logging import get_request_id

        try:
            return self._primary.chat(query, context_chunks)
        except Exception as e:
            logger.warning(
                "Primary LLM failed after retries, switching to fallback. "
                "error=%s request_id=%s",
                type(e).__name__,
                get_request_id(),
            )
            return self._fallback.chat(query, context_chunks)

    def stream_chat(self, query: str, context_chunks: list[str]) -> Iterator[str]:
        from app.core.logging import get_request_id

        try:
            # 初始化迭代器（此时未触发实际请求）
            primary_iter = self._primary.stream_chat(query, context_chunks)
            # next() 触发真实网络请求，若 primary 有问题大概率在此处抛出
            first_token = next(primary_iter)
        except Exception as e:
            logger.warning(
                "Primary stream_chat failed, switching to fallback. "
                "error=%s request_id=%s",
                type(e).__name__,
                get_request_id(),
            )
            yield from self._fallback.stream_chat(query, context_chunks)
            return

        yield first_token
        yield from primary_iter

    def complete(self, prompt: str, temperature: float = 0.0) -> str:
        from app.core.logging import get_request_id

        try:
            return self._primary.complete(prompt, temperature=temperature)
        except Exception as e:
            logger.warning(
                "Primary LLM failed after retries, switching to fallback. "
                "error=%s request_id=%s",
                type(e).__name__,
                get_request_id(),
            )
            return self._fallback.complete(prompt, temperature=temperature)
    
    def choose_tool(self, query: str, tools: list[dict]) -> tuple[str, dict] | None:
        from app.core.logging import get_request_id

        try:
            return self._primary.choose_tool(query, tools)
        except Exception as e:
            logger.warning(
                "Primary LLM failed after retries, switching to fallback. "
                "error=%s request_id=%s",
                type(e).__name__,
                get_request_id(),
            )
            return self._fallback.choose_tool(query, tools)
    
    def agent_step(self, messages: list[dict], tools: list[dict]) -> dict:
        from app.core.logging import get_request_id

        try:
            return self._primary.agent_step(messages, tools)
        except Exception as e:
            logger.warning(
                "Primary LLM failed after retries, switching to fallback. "
                "error=%s request_id=%s",
                type(e).__name__,
                get_request_id(),
            )
            return self._fallback.agent_step(messages, tools)


_instance: LLMClient | None = None

def get_llm_service(settings) -> LLMClient:
    global _instance
    if _instance is None:
        if settings.llm_mode == "mock":
            _instance = MockLLMService()
        elif settings.llm_backend == "remote":
            _instance = ResilientLLMService(
                primary=RemoteLLMService(settings.model_service_url, settings.llm_timeout),
                fallback=MockLLMService(),
            )
        else:
            _instance = ResilientLLMService(
                primary=OpenAILLMService(
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url,
                    model=settings.llm_model,
                    timeout=settings.llm_timeout,
                    max_retries=settings.llm_max_retries,
                ),
                fallback=MockLLMService(),
            )
    return _instance
