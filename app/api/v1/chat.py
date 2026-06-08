import logging

from fastapi import APIRouter, HTTPException

from app.schemas.chat import ChatRequest, ChatResponse
from app.services import rag_service

router = APIRouter()
logger = logging.getLogger(__name__)

_FALLBACK_ANSWER = "服务暂时繁忙，请稍后重试。"

try:
    import openai as _openai
    _TRANSIENT_ERRORS = (
        _openai.APITimeoutError,
        _openai.APIConnectionError,
        _openai.RateLimitError,
    )
except ImportError:
    _TRANSIENT_ERRORS = ()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        result = rag_service.chat(request.query, request.top_k)
        return ChatResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except _TRANSIENT_ERRORS as e:
        logger.warning("LLM transient error [%s]: %s", type(e).__name__, e)
        return ChatResponse(
            answer=_FALLBACK_ANSWER,
            retrieved_chunks=[],
            error="llm_unavailable",
        )
    except Exception as e:
        logger.error("Chat failed [%s]: %s", type(e).__name__, e)
        return ChatResponse(
            answer=_FALLBACK_ANSWER,
            retrieved_chunks=[],
            error="internal_error",
        )
