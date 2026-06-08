import logging
from typing import cast

import redis as _redis

from app.core.errors import AppError

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, redis_url: str, limit: int, window: int):
        self._client = _redis.from_url(redis_url, socket_connect_timeout=2)
        self._limit = limit
        self._window = window

    def check(self, identifier: str) -> None:
        """Raise AppError(429) if identifier has exceeded the rate limit.
        Fails open on Redis errors so a Redis outage does not block all requests.
        """
        key = f"rl:{identifier}"
        try:
            count = cast(int, self._client.incr(key))
            if count == 1:
                self._client.expire(key, self._window)
        except Exception as e:
            logger.warning("Rate limiter Redis error, skipping check: %s", e)
            return

        if count > self._limit:
            raise AppError(
                error_code="RATE_LIMITED",
                message=f"Rate limit exceeded. Max {self._limit} requests per {self._window}s.",
                status_code=429,
                details={"limit": self._limit, "window_seconds": self._window},
            )


_instance: RateLimiter | None = None


def get_rate_limiter(settings) -> RateLimiter:
    global _instance
    if _instance is None:
        _instance = RateLimiter(
            redis_url=settings.redis_url,
            limit=settings.rate_limit_requests,
            window=settings.rate_limit_window,
        )
    return _instance
