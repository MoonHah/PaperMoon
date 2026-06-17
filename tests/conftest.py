"""
Shared fixtures for all main-app integration tests.

Key design decisions:
- env vars are set BEFORE any app import so Settings() sees them at construction time
- StaticPool ensures all SQLite connections share the same in-memory database
- mock_store must be set before TestClient starts (lifespan calls ensure_collection)
- autouse _reset_singletons prevents singleton leakage between tests
"""

import os

# Override env vars before any app module is imported.
# pydantic-settings gives env vars priority over .env file.
os.environ["LLM_MODE"] = "mock"
os.environ["EMBEDDING_MODE"] = "mock"
os.environ["RATE_LIMIT_ENABLED"] = "false"
# 给测试设真 JWT_SECRET：lifespan 安全闸在非 debug 下会拒绝默认密钥启动（TestClient 会触发 lifespan）。
os.environ["JWT_SECRET"] = "test-jwt-secret-32bytes-minimum-abcdef0123456789"

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base, get_db
from app.main import app
import app.core.rate_limit as _rl_module
import app.services.embedding_service as _emb_module
import app.services.llm_service as _llm_module
import app.services.vector_store as _vs_module

# ── Shared SQLite engine ─────────────────────────────────────────────────────
# StaticPool: all connections (including those created inside task functions)
# share the exact same in-memory database, so writes are immediately visible
# across sessions without needing a file on disk.
_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(bind=_TEST_ENGINE, autocommit=False, autoflush=False)


# ── In-memory VectorStore ────────────────────────────────────────────────────

class InMemoryVectorStore:
    """Minimal in-memory implementation of the VectorStore protocol."""

    def __init__(self) -> None:
        self._docs: list[dict] = []

    def ensure_collection(self) -> None:
        pass

    def upsert(
        self,
        document_id: str,
        filename: str,
        chunks: list[str],
        embeddings: list[list[float]],
        user_id: str = "test-user",
    ) -> None:
        # user_id 设默认值，方便测试用关键字调用；单元测试不验证向量层的多租户过滤
        # （文档归属隔离由 test_documents 覆盖，检索隔离在真实 Qdrant 端到端验证）。
        for chunk in chunks:
            self._docs.append(
                {"document_id": document_id, "filename": filename, "chunk_text": chunk}
            )

    def delete_by_document_id(self, document_id: str) -> None:
        self._docs = [d for d in self._docs if d["document_id"] != document_id]

    def search(self, query_embedding: list[float], top_k: int) -> list[str]:
        return [d["chunk_text"] for d in self._docs[:top_k]]

    def search_with_metadata(
        self, query_embedding: list[float], top_k: int, user_id: str | None = None
    ) -> list[dict]:
        # 忽略 user_id 过滤（见 upsert 注释）：保持检索 mechanics 测试不受多租户影响
        return [
            {
                "text": d["chunk_text"],
                "document_id": d["document_id"],
                "filename": d["filename"],
            }
            for d in self._docs[:top_k]
        ]

    def count(self) -> int:
        return len(self._docs)


# ── autouse fixtures (run for every test automatically) ──────────────────────

@pytest.fixture(autouse=True)
def _reset_singletons() -> Generator[None, None, None]:
    """Clear all module-level service singletons before and after each test."""
    _vs_module._instance = None
    _llm_module._instance = None
    _emb_module._instance = None
    _rl_module._instance = None
    yield
    _vs_module._instance = None
    _llm_module._instance = None
    _emb_module._instance = None
    _rl_module._instance = None


@pytest.fixture(autouse=True)
def _db_tables() -> Generator[None, None, None]:
    """Create all ORM tables before each test and drop them after."""
    Base.metadata.create_all(bind=_TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=_TEST_ENGINE)


@pytest.fixture(autouse=True)
def _mock_celery(monkeypatch) -> None:
    """Prevent process_document.delay() from connecting to a real Celery broker."""
    import app.workers.document_tasks as _tasks

    class _FakeTask:
        id = "fake-celery-task-id"

    monkeypatch.setattr(_tasks.process_document, "delay", lambda _doc_id: _FakeTask())


# ── Named fixtures (requested explicitly by tests) ───────────────────────────

@pytest.fixture
def mock_store() -> InMemoryVectorStore:
    """
    Register an InMemoryVectorStore as the active singleton.
    Must be set before TestClient starts because app lifespan calls ensure_collection().
    """
    store = InMemoryVectorStore()
    _vs_module._instance = store
    return store


@pytest.fixture
def tmp_storage(tmp_path, monkeypatch):
    """Point settings.storage_path to a per-test temp directory."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "storage_path", str(tmp_path))
    return tmp_path


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Direct SQLite session for test setup (pre-inserting records)."""
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def anon_client(mock_store, tmp_storage) -> Generator[TestClient, None, None]:
    """未认证 TestClient（认证流程 / 401 用例）。

    Wired to: SQLite (dependency_overrides[get_db]) + InMemoryVectorStore + 临时文件存储。
    """

    def _get_db_override() -> Generator[Session, None, None]:
        db = _TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client(anon_client: TestClient) -> TestClient:
    """默认已登录的 TestClient：注册一个测试用户并带上 Bearer 头。

    本应用几乎所有业务端点都需登录，故默认 client 即认证态；
    认证流程本身与 401 用例改用 anon_client。
    """
    creds = {"email": "tester@example.com", "password": "secret123"}
    anon_client.post("/api/v1/auth/register", json=creds)
    token = anon_client.post("/api/v1/auth/login", json=creds).json()["access_token"]
    anon_client.headers.update({"Authorization": f"Bearer {token}"})
    return anon_client
