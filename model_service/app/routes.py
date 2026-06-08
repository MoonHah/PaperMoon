import json
import logging
from typing import cast

import openai
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from openai.types.chat import ChatCompletionMessageParam
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.schemas import EmbedRequest, EmbedResponse, GenerateRequest, GenerateResponse, TokenUsage

router = APIRouter()
logger = logging.getLogger(__name__)

_RETRY_ON = (openai.APITimeoutError, openai.APIConnectionError, openai.RateLimitError)

# Module-level client — reuses connection pool across requests
_client = openai.OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)


@router.post("/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest) -> GenerateResponse:
    @retry(
        retry=retry_if_exception_type(_RETRY_ON),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(settings.llm_max_retries),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _call() -> GenerateResponse:
        resp = _client.chat.completions.create(
            model=settings.llm_model,
            messages=cast(
                list[ChatCompletionMessageParam],
                [{"role": m.role, "content": m.content} for m in request.messages],
            ),
            timeout=settings.llm_timeout,
        )
        usage = None
        if resp.usage:
            usage = TokenUsage(
                prompt_tokens=resp.usage.prompt_tokens,
                completion_tokens=resp.usage.completion_tokens,
                total_tokens=resp.usage.total_tokens,
            )
        return GenerateResponse(content=resp.choices[0].message.content or "", usage=usage)

    try:
        result = _call()
        logger.info("generate.ok", extra={"model": settings.llm_model})
        return result
    except Exception as e:
        logger.error("generate.failed", extra={"error": type(e).__name__})
        raise HTTPException(status_code=502, detail=f"LLM call failed: {type(e).__name__}")


@router.post("/generate/stream")
def generate_stream(request: GenerateRequest) -> StreamingResponse:
    def sse_gen():
        try:
            stream = _client.chat.completions.create(
                model=settings.llm_model,
                messages=cast(
                    list[ChatCompletionMessageParam],
                    [{"role": m.role, "content": m.content} for m in request.messages],
                ),
                timeout=settings.llm_timeout,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield f"data: {json.dumps({'token': delta})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error("generate_stream.failed", extra={"error": type(e).__name__})
            yield f"data: {json.dumps({'error': type(e).__name__})}\n\n"

    return StreamingResponse(sse_gen(), media_type="text/event-stream")

@router.post("/embed", response_model=EmbedResponse)
def embed(request: EmbedRequest) -> EmbedResponse:
    @retry(
        retry=retry_if_exception_type(_RETRY_ON),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(settings.embedding_max_retries),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _call() -> list[float]:
        resp = _client.embeddings.create(
            input=request.text,
            model=settings.embedding_model,
            timeout=settings.embedding_timeout,
        )
        return resp.data[0].embedding

    try:
        embedding = _call()
        return EmbedResponse(embedding=embedding)
    except Exception as e:
        logger.error("embed.failed", extra={"error": type(e).__name__})
        raise HTTPException(status_code=502, detail=f"Embedding call failed: {type(e).__name__}")


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@router.get("/ready")
def ready() -> dict:
    openai_configured = bool(settings.openai_api_key)
    return {
        "status": "ok" if openai_configured else "degraded",
        "openai": "configured" if openai_configured else "missing_api_key",
    }
