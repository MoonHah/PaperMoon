"""
Fixtures for model-service tests.

Run these tests from the model_service/ directory:
  cd model_service && python -m pytest

The pyproject.toml in model_service/ sets pythonpath = ["."] so that
'from app.xxx import ...' resolves to model_service/app/, not the main app.
"""

import os

# routes.py creates openai.OpenAI(api_key=settings.openai_api_key) at import time.
# The OpenAI SDK (v2+) rejects an empty api_key at construction — set a dummy key
# so the module loads.  The actual _client is replaced by fixtures before any call.
os.environ.setdefault("OPENAI_API_KEY", "sk-dummy-key-for-testing")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def model_client() -> TestClient:
    from app.main import app  # model_service/app/main.py

    with TestClient(app) as c:
        yield c


# ── Fake OpenAI client objects ───────────────────────────────────────────────

class _FakeChatCompletion:
    class _Choice:
        class message:
            content = "Mocked LLM response"

    choices = [_Choice()]
    usage = None


class _FakeEmbeddingResponse:
    class _Data:
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

    data = [_Data()]


class _MockOpenAIClient:
    class chat:
        class completions:
            @staticmethod
            def create(**kwargs):
                return _FakeChatCompletion()

    class embeddings:
        @staticmethod
        def create(**kwargs):
            return _FakeEmbeddingResponse()


class _FailingOpenAIClient:
    class chat:
        class completions:
            @staticmethod
            def create(**kwargs):
                # Raise a plain Exception (not in _RETRY_ON) so tenacity does NOT retry
                raise RuntimeError("Simulated OpenAI outage")

    class embeddings:
        @staticmethod
        def create(**kwargs):
            raise RuntimeError("Simulated OpenAI outage")


@pytest.fixture
def mock_openai(monkeypatch):
    """Replace routes._client with a fake that returns controlled responses."""
    import app.routes as routes_mod

    monkeypatch.setattr(routes_mod, "_client", _MockOpenAIClient())


@pytest.fixture
def failing_openai(monkeypatch):
    """Replace routes._client with a fake that always raises an exception."""
    import app.routes as routes_mod

    monkeypatch.setattr(routes_mod, "_client", _FailingOpenAIClient())
