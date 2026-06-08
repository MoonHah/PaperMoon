import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

_CHECK_TIMEOUT = 2.0


def _check_with_timeout(fn, timeout: float = _CHECK_TIMEOUT) -> str:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError:
            return "timeout"
        except Exception as e:
            logger.warning("Dependency check failed: %s", e)
            return "error"


def _check_postgres() -> str:
    from sqlalchemy import text
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return "ok"
    finally:
        db.close()


def _check_qdrant() -> str:
    from app.services.vector_store import get_vector_store
    get_vector_store(settings).count()
    return "ok"


def _check_redis() -> str:
    import redis
    client = redis.from_url(settings.redis_url, socket_connect_timeout=2)
    client.ping()
    return "ok"


class LivenessResponse(BaseModel):
    status: str
    app_name: str
    app_version: str


class DependencyStatus(BaseModel):
    postgres: str
    qdrant: str
    redis: str


class ReadinessResponse(BaseModel):
    status: str
    dependencies: DependencyStatus


@router.get("/health", response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    """Liveness probe: is the process alive? No dependency checks."""
    return LivenessResponse(
        status="ok",
        app_name=settings.app_name,
        app_version=settings.app_version,
    )


@router.get("/ready", response_model=ReadinessResponse)
def readiness() -> ReadinessResponse:
    """Readiness probe: can the service handle traffic? Checks all dependencies."""
    deps = DependencyStatus(
        postgres=_check_with_timeout(_check_postgres),
        qdrant=_check_with_timeout(_check_qdrant),
        redis=_check_with_timeout(_check_redis),
    )
    all_ok = all(v == "ok" for v in deps.model_dump().values())
    return ReadinessResponse(
        status="ok" if all_ok else "degraded",
        dependencies=deps,
    )
