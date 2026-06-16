from fastapi import APIRouter

from app.agent import graph_agent
from app.agent.schemas import AgentRunRequest, AgentRunResponse

router = APIRouter()


@router.post("/agent/run", response_model=AgentRunResponse)
def agent_run(request: AgentRunRequest) -> AgentRunResponse:
    # 统一后端：LangGraph 版 ReAct agent（手写版已下线）。
    return graph_agent.run(request)
