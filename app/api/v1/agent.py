from fastapi import APIRouter, Depends

from app.agent import graph_agent
from app.agent.schemas import AgentRunRequest, AgentRunResponse
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/agent/run", response_model=AgentRunResponse)
def agent_run(
    request: AgentRunRequest, user: User = Depends(get_current_user)
) -> AgentRunResponse:
    # 统一后端：LangGraph 版 ReAct agent（手写版已下线）。user_id 用于按用户隔离。
    return graph_agent.run(request, user.id)
