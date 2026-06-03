from fastapi import FastAPI

from app.api.v1.router import v1_router
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

app.include_router(
    v1_router,
    prefix="/api/v1",
)


# ================= 启动服务 ==================
def main() -> None:
    """
    启动服务: uv run start
    """
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True) # reload 先用 true, 落地后改回


if __name__ == "__main__":
    main()