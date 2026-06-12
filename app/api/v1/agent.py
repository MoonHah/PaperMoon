from fastapi import APIRouter
from app.agent.schemas import AgentRunRequest, AgentRunResponse
from app.agent import agent_service
from app.core.config import settings
from app.agent import graph_agent

router = APIRouter()

@router.post("/agent/run", response_model=AgentRunResponse)
def agent_run(request: AgentRunRequest) -> AgentRunResponse:
    if settings.agent_backend == "langgraph":
        return graph_agent.run(request)
    return agent_service.run(request)