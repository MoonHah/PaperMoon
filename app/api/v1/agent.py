import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agent import graph_agent
from app.agent.schemas import AgentRunRequest, AgentRunResponse, CitedChunk, IntermediateStep
from app.core import database
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services import conversation_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/agent/run", response_model=AgentRunResponse)
def agent_run(
    request: AgentRunRequest,
    session: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentRunResponse:
    # 同步端点：一次性返回完整 AgentRunResponse（作为可测的简单契约）。user_id 用于按用户隔离。
    response = graph_agent.run(request, user.id)
    # 成功才落库会话转录（供历史侧栏）。持久化失败不影响对话返回——agent 与会话存储解耦。
    if response.error is None and response.session_id:
        try:
            conversation_service.record_turn(
                session, user.id, response.session_id, request.user_query, response
            )
        except Exception as e:
            logger.warning("record conversation failed [%s]: %s", type(e).__name__, e)
    return response


def _persist_stream_turn(request: AgentRunRequest, user_id: str, final_event: dict) -> None:
    """流式收尾落库：用 fresh SessionLocal（不能用 get_db——流式在请求返回后才迭代，
    那时 get_db 的 session 已关闭）。失败只记日志，不影响已发完的流。"""
    try:
        session_id: str = final_event["session_id"]  # run_stream 必定带（非空），用它避免 str|None 收窄
        response = AgentRunResponse(
            final_answer=final_event["final_answer"],
            selected_tool="(final)",
            intermediate_steps=[IntermediateStep(**s) for s in final_event.get("steps", [])],
            citations=[CitedChunk(**c) for c in final_event.get("citations", [])],
            session_id=session_id,
        )
        db = database.SessionLocal()
        try:
            conversation_service.record_turn(
                db, user_id, session_id, request.user_query, response
            )
        finally:
            db.close()
    except Exception as e:
        logger.warning("record stream conversation failed [%s]: %s", type(e).__name__, e)


@router.post("/agent/run/stream")
def agent_run_stream(
    request: AgentRunRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """流式端点（SSE）：把推理轨迹逐步推给前端，最终答案整块给。供 UI 实时展示。
    与同步 /agent/run 共享 graph_agent 核心逻辑，仅传输形态不同。"""

    def sse():
        final_event: dict | None = None
        try:
            for event in graph_agent.run_stream(request, user.id):
                if event.get("type") == "final":
                    final_event = event
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error("agent stream endpoint failed [%s]: %s", type(e).__name__, e)
            yield f'data: {json.dumps({"type": "error", "message": "服务暂时繁忙，请稍后重试。"}, ensure_ascii=False)}\n\n'
        # 仅在流正常产出 final 时落库（run_stream 内部出错会发 error 事件、不置 final_event）
        if final_event is not None:
            _persist_stream_turn(request, user.id, final_event)
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")
