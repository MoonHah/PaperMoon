from fastapi import APIRouter


from app.api.v1 import (
    health,
    documents,
    chat,
    agent,
    auth,
)

v1_router = APIRouter()     # v1 的父router

v1_router.include_router(
    health.router,
    tags=["health"],    # 在 FastAPI 的 /docs 文档里，把这个接口归类到 health 分组下面
)

v1_router.include_router(
    auth.router,
    tags=["auth"],
)

v1_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["documents"]
)

v1_router.include_router(
    chat.router,
    tags=["chat"]
)

v1_router.include_router(
    agent.router,
    tags=["agent"],
)