"""
Integration tests for document_tasks.process_document.

Key setup:
- document_tasks.SessionLocal is monkeypatched to _TestSession (SQLite)
- _vs_module._instance is set to InMemoryVectorStore before the task runs
- The task is invoked via .run() which bypasses the Celery broker entirely
"""

import pytest

from app.models.document import DocumentStatus
from app.repositories import document_repository
import app.services.vector_store as _vs_module
import app.workers.document_tasks as _tasks_module
from tests.conftest import InMemoryVectorStore, _TestSession


@pytest.fixture
def task_env(tmp_path, monkeypatch, db_session):
    """
    Wire everything the Celery task needs to run in-process with SQLite + temp storage.

    Returns (document_id, store) so callers can pre-create files and later verify state.
    """
    from app.core.config import settings

    # 1. Redirect file I/O to a temp directory
    monkeypatch.setattr(settings, "storage_path", str(tmp_path))

    # 2. Patch document_tasks.SessionLocal → SQLite (not app.core.database.SessionLocal,
    #    because document_tasks already has its own reference after the import)
    monkeypatch.setattr(_tasks_module, "SessionLocal", _TestSession)

    # 3. Set the vector store singleton to our in-memory implementation
    store = InMemoryVectorStore()
    _vs_module._instance = store

    # 4. Pre-create a document record in SQLite
    doc_id = "task-test-doc-001"
    document_repository.create(
        db_session, document_id=doc_id, user_id="task-test-user",
        filename="sample.txt", file_type=".txt"
    )
    db_session.commit()

    # 5. Write the actual file the task will read
    (tmp_path / f"{doc_id}.txt").write_text(
        "Python is a high-level programming language. "
        "It emphasizes code readability and simplicity. "
        "Python supports multiple programming paradigms."
    )

    return doc_id, store


def test_process_document_sets_status_to_ready(task_env):
    doc_id, store = task_env

    result = _tasks_module.process_document.run(doc_id)

    # Task return value
    assert result["document_id"] == doc_id
    assert result["chunk_count"] > 0

    # DB record updated to READY
    db = _TestSession()
    updated = document_repository.get_by_id(db, doc_id)
    db.close()
    assert updated is not None
    assert updated.status == DocumentStatus.READY.value
    assert updated.chunk_count is not None and updated.chunk_count > 0


def test_process_document_upserts_vectors(task_env):
    doc_id, store = task_env

    assert store.count() == 0
    _tasks_module.process_document.run(doc_id)
    assert store.count() > 0


def test_process_document_missing_file_raises(task_env, tmp_path):
    doc_id, _ = task_env

    # Delete the file so the task can't read it
    (tmp_path / f"{doc_id}.txt").unlink()

    with pytest.raises(Exception):
        _tasks_module.process_document.run(doc_id)


def test_process_document_unknown_id_raises(task_env, monkeypatch, tmp_path):
    _, _ = task_env

    with pytest.raises(Exception, match="not found"):
        _tasks_module.process_document.run("this-id-does-not-exist")
