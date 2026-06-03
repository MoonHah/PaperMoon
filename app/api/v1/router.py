from fastapi import APIRouter

from app.core.config import settings


from app.api.v1 import (
    health
)

v1_router = APIRouter()     # v1 的父router

v1_router.include_router(
    health.router,
    tags=["health"],    # 在 FastAPI 的 /docs 文档里，把这个接口归类到 health 分组下面
)




if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.service:app", host=settings.host, port=settings.port, reload=False) 