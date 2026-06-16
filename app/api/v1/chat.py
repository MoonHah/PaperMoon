import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import rag_service
from app.services.vector_store import get_vector_store

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat")
def chat(
    request: ChatRequest,
    stream: bool = False,
    user: User = Depends(get_current_user),
):
    user_id = user.id
    if stream:
        if get_vector_store(settings).count() == 0:
            raise HTTPException(status_code=400, detail="No documents uploaded yet.")

        def sse_gen():
            # 流式过程中的异常（检索/embedding/LLM 失败）必须在流内兜住：
            # 否则 SSE 会无 [DONE] 裸断，客户端挂起等待。
            try:
                for token in rag_service.stream_chat(request.query, request.top_k, user_id):
                    yield f'data: {json.dumps({"token": token})}\n\n'
            except Exception as e:
                logger.error("Stream chat failed [%s]: %s", type(e).__name__, e)
                yield f'data: {json.dumps({"error": "服务暂时繁忙，请稍后重试。"})}\n\n'
            yield "data: [DONE]\n\n"

        return StreamingResponse(sse_gen(), media_type="text/event-stream")

    try:
        result = rag_service.chat(request.query, request.top_k, user_id)
        return ChatResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Chat failed [%s]: %s", type(e).__name__, e)
        return ChatResponse(
            answer="服务暂时繁忙，请稍后重试。",
            retrieved_chunks=[],
            error="internal_error",
        )
