import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.errors import AppError, app_error_response
from app.core.logging import set_request_id

logger = logging.getLogger(__name__)


class RequestMiddleware(BaseHTTPMiddleware):
    """Generates or propagates X-Request-ID and injects it into the logging ContextVar."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:8]
        set_request_id(request_id)

        t_start = time.perf_counter()
        logger.info("request.start", extra={"method": request.method, "path": request.url.path})

        response = await call_next(request)

        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
        logger.info(
            "request.end",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
            },
        )
        response.headers["X-Request-ID"] = request_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP (or X-User-ID) rate limiting backed by Redis. Fails open on Redis errors."""

    async def dispatch(self, request: Request, call_next) -> Response:
        from app.core.config import settings

        if not settings.rate_limit_enabled:
            return await call_next(request)

        from app.core.rate_limit import get_rate_limiter

        identifier = request.headers.get("X-User-ID") or (
            request.client.host if request.client else "unknown"
        )
        try:
            get_rate_limiter(settings).check(identifier)
        except AppError as e:
            # 复用统一错误响应；X-Request-ID 由外层 RequestMiddleware 统一补上。
            return app_error_response(e)
        return await call_next(request)
