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
    ) -> None:
        for chunk in chunks:
            self._docs.append(
                {"document_id": document_id, "filename": filename, "chunk_text": chunk}
            )

    def delete_by_document_id(self, document_id: str) -> None:
        self._docs = [d for d in self._docs if d["document_id"] != document_id]

    def search(self, query_embedding: list[float], top_k: int) -> list[str]:
        return [d["chunk_text"] for d in self._docs[:top_k]]

    def search_with_metadata(
        self, query_embedding: list[float], top_k: int
    ) -> list[dict]:
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
def client(mock_store, tmp_storage) -> Generator[TestClient, None, None]:
    """
    TestClient wired to:
    - SQLite (via dependency_overrides[get_db])
    - InMemoryVectorStore (via mock_store, which sets _vs_module._instance)
    - Temp file storage (via tmp_storage)
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
