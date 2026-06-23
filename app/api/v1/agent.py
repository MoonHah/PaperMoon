import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agent import graph_agent
from app.agent.schemas import AgentRunRequest, AgentRunResponse
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
    # 统一后端：LangGraph 版 ReAct agent（手写版已下线）。user_id 用于按用户隔离。
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
