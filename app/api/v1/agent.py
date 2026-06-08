from fastapi import APIRouter
from app.agent.schemas import AgentRunRequest, AgentRunResponse
from app.agent import agent_service

router = APIRouter()

@router.post("/agent/run", response_model=AgentRunResponse)
def agent_run(request: AgentRunRequest) -> AgentRunResponse:
    return agent_service.run(request)