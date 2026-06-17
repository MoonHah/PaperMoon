from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import v1_router
from app.core.config import DEV_JWT_SECRET, settings
from app.core.errors import AppError, app_error_handler, http_exception_handler, validation_error_handler
from app.core.logging import setup_logging
from app.core.middleware import RateLimitMiddleware, RequestMiddleware
from app.services.vector_store import get_vector_store

setup_logging(level=settings.log_level, service=settings.app_name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 安全闸：非 debug 下若 JWT_SECRET 仍是开发默认值，拒绝启动——
    # 否则任何人都能用已知密钥伪造任意用户的 token。
    if not settings.debug and settings.jwt_secret == DEV_JWT_SECRET:
        raise RuntimeError(
            "拒绝启动：JWT_SECRET 仍是开发默认值且 DEBUG=false。"
            "请设置强随机的 JWT_SECRET 环境变量（≥32 字节）后再启动。"
        )
    get_vector_store(settings).ensure_collection()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

# Exception handlers — convert all errors to {"error_code", "message", "details"}
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)

# Middleware — registration order is reverse execution order:
# RateLimitMiddleware registered first → innermost → runs AFTER RequestMiddleware
# RequestMiddleware registered second → outermost → runs FIRST (sets request_id)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestMiddleware)

app.include_router(
    v1_router,
    prefix="/api/v1",
)


def main() -> None:
    """
    启动服务: uv run start
    """
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)


if __name__ == "__main__":
    main()
