import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.errors import AppError
from app.core.logging import get_request_id, set_request_id

logger = logging.getLogger(__name__)


class RequestMiddleware(BaseHTTPMiddleware):
    """Generates or propagates X-Request-ID and injects it into the logging ContextVar."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:8]
        set_request_id(request_id)
        logger.info("→ %s %s", request.method, request.url.path)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info("← %s %s %d", request.method, request.url.path, response.status_code)
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
            return JSONResponse(
                status_code=e.status_code,
                content={"error_code": e.error_code, "message": e.message, "details": e.details},
                headers={"X-Request-ID": get_request_id()},
            )
        return await call_next(request)
