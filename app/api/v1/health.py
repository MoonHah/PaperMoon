from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings   

router = APIRouter()    # 创建一个路由对象

# =============== HealthResponse =================
class HealthResponse(BaseModel):
    status: str
    app_name: str
    app_version: str
    

# =============== 定义 GET /health 接口 ============
@router.get("/health", response_model=HealthResponse)  # 把 /health 接口注册到这个 router 上, 而不是 app 上
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        app_version=settings.app_version,
    )