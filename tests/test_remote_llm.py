"""
Tests for RemoteLLMService and ResilientLLMService fallback behaviour.

Uses pytest-httpx to intercept httpx.Client requests without a real HTTP server.

Key concept: RemoteLLMService wraps httpx.Client; pytest-httpx's httpx_mock fixture
intercepts those calls at the transport level, so no network socket is opened.
"""

import pytest


@pytest.fixture(autouse=True)
def _reset_llm_singleton():
    """Extra guard: ensure the LLM singleton is clean before each test."""
    import app.services.llm_service as mod
    mod._instance = None
    yield
    mod._instance = None


def test_remote_llm_parses_content_field(httpx_mock):
    from app.services.llm_service import RemoteLLMService

    httpx_mock.add_response(
        method="POST",
        url="http://fake-model/generate",
        json={"content": "Python is a versatile language.", "usage": None},
        status_code=200,
    )

    service = RemoteLLMService(base_url="http://fake-model", timeout=5.0)
    result = service.chat("What is Python?", ["Python context chunk."])
    assert result == "Python is a versatile language."


def test_remote_llm_forwards_request_id_header(httpx_mock):
    from app.services.llm_service import RemoteLLMService

    httpx_mock.add_response(
        method="POST",
        url="http://fake-model/generate",
        json={"content": "ok", "usage": None},
    )

    service = RemoteLLMService(base_url="http://fake-model", timeout=5.0)
    service.chat("hello", ["context"])

    requests = httpx_mock.get_requests()
    assert len(requests) == 1
    assert "X-Request-ID" in requests[0].headers


def test_resilient_llm_falls_back_on_502(httpx_mock):
    """If the primary (remote) returns 502, ResilientLLMService uses MockLLMService."""
    from app.services.llm_service import MockLLMService, RemoteLLMService, ResilientLLMService

    httpx_mock.add_response(
        method="POST",
        url="http://fake-model/generate",
        status_code=502,
    )

    primary = RemoteLLMService(base_url="http://fake-model", timeout=5.0)
    fallback = MockLLMService()
    resilient = ResilientLLMService(primary=primary, fallback=fallback)

    result = resilient.chat("What is Go?", ["Go is a compiled language."])
    # MockLLMService always starts its response with "[MOCK]"
    assert "[MOCK]" in result


def test_resilient_llm_uses_primary_on_success(httpx_mock):
    from app.services.llm_service import MockLLMService, RemoteLLMService, ResilientLLMService

    httpx_mock.add_response(
        method="POST",
        url="http://fake-model/generate",
        json={"content": "Primary response here.", "usage": None},
    )

    primary = RemoteLLMService(base_url="http://fake-model", timeout=5.0)
    resilient = ResilientLLMService(primary=primary, fallback=MockLLMService())

    result = resilient.chat("question", ["context"])
    assert result == "Primary response here."
    assert "[MOCK]" not in result
