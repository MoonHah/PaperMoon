import json
import logging
from typing import cast

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = 400,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def _body(error_code: str, message: str, details: dict) -> dict:
    return {"error_code": error_code, "message": message, "details": details}


def app_error_response(exc: AppError) -> JSONResponse:
    """把 AppError 渲染成统一错误响应。异常处理器与限流中间件共用，避免重复构造响应体。"""
    return JSONResponse(
        status_code=exc.status_code,
        content=_body(exc.error_code, exc.message, exc.details),
    )


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return app_error_response(cast(AppError, exc))


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    e = cast(StarletteHTTPException, exc)
    return JSONResponse(
        status_code=e.status_code,
        content=_body(f"HTTP_{e.status_code}", str(e.detail), {}),
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    e = cast(RequestValidationError, exc)
    logger.warning("Validation error on %s: %s", request.url.path, e.errors())
    # Pydantic v2 error dicts may contain non-serializable objects (e.g. ValueError in 'ctx').
    # Pre-serialize with default=str to convert them to strings.
    safe_errors = json.loads(json.dumps(e.errors(), default=str))
    return JSONResponse(
        status_code=422,
        content=_body("VALIDATION_ERROR", "Request validation failed", {"errors": safe_errors}),
    )
