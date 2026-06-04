from fastapi import APIRouter, HTTPException

from app.schemas.chat import ChatRequest, ChatResponse
from app.services import rag_service

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        result = rag_service.chat(request.query, request.top_k)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ChatResponse(**result)
