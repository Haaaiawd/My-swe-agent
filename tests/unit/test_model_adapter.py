"""Unit tests for ModelAdapter.

Uses monkeypatching to mock litellm.completion and completion_cost.
Covers: normal call, retry exhaustion, cost_missing warn/error strategies,
cost_calculation_method field.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from core.model_adapter import call_model
from core.models import CostMissingError, ModelResponse


class MockChoice:
    def __init__(self, content: str = "hi", tool_calls: list | None = None) -> None:
        self.message = MagicMock()
        self.message.content = content
        self.message.tool_calls = tool_calls or []
        self.message.model_dump.return_value = {
            "content": content,
            "tool_calls": tool_calls or [],
            "role": "assistant",
        }


class MockResponse:
    def __init__(self, cost: float | None = 0.01, content: str = "hi") -> None:
        self._response_cost = cost
        self.choices = [MockChoice(content)]


def test_normal_call_with_api_cost(monkeypatch):
    def mock_completion(*, model, messages, api_key, **kwargs):
        return MockResponse(cost=0.01, content="hello")

    monkeypatch.setattr("core.model_adapter.litellm.completion", mock_completion)

    result = call_model(
        messages=[{"role": "user", "content": "test"}],
        config={"model": {"name": "gpt-4o", "api_key": "sk-test"}},
    )
    assert isinstance(result, ModelResponse)
    assert result.cost == pytest.approx(0.01)
    assert result.message["cost_calculation_method"] == "api"


def test_retry_exhaustion(monkeypatch):
    import litellm

    call_count = 0

    def mock_completion(*, model, messages, api_key, **kwargs):
        nonlocal call_count
        call_count += 1
        raise litellm.Timeout(
            message="timed out",
            model="gpt-4o",
            llm_provider="openai",
        )

    monkeypatch.setattr("core.model_adapter.litellm.completion", mock_completion)

    with pytest.raises(litellm.Timeout):
        call_model(
            messages=[{"role": "user", "content": "test"}],
            config={"model": {"name": "gpt-4o", "api_key": "sk-test"}},
        )
    # 1 initial + 4 retries = 5 total attempts
    assert call_count == 5


def test_cost_missing_warn(monkeypatch):
    def mock_completion(*, model, messages, api_key, **kwargs):
        return MockResponse(cost=None, content="hello")

    def mock_cost(*args, **kwargs):
        raise RuntimeError("no cost")

    monkeypatch.setattr("core.model_adapter.litellm.completion", mock_completion)
    monkeypatch.setattr("core.model_adapter.litellm.completion_cost", mock_cost)

    result = call_model(
        messages=[{"role": "user", "content": "test"}],
        config={"model": {"name": "gpt-4o", "cost_missing_strategy": "warn"}},
    )
    assert result.cost == pytest.approx(0.0)
    assert result.message["cost_calculation_method"] == "missing"


def test_cost_missing_error(monkeypatch):
    def mock_completion(*, model, messages, api_key, **kwargs):
        return MockResponse(cost=None, content="hello")

    def mock_cost(*args, **kwargs):
        raise RuntimeError("no cost")

    monkeypatch.setattr("core.model_adapter.litellm.completion", mock_completion)
    monkeypatch.setattr("core.model_adapter.litellm.completion_cost", mock_cost)

    with pytest.raises(CostMissingError):
        call_model(
            messages=[{"role": "user", "content": "test"}],
            config={"model": {"name": "gpt-4o", "cost_missing_strategy": "error"}},
        )


# ── Streaming tests ─────────────────────────────────────────────


class MockDelta:
    def __init__(self, content: str) -> None:
        self.content = content


class MockStreamChoice:
    def __init__(self, content: str) -> None:
        self.delta = MockDelta(content)


class MockStreamChunk:
    def __init__(self, content: str) -> None:
        self.choices = [MockStreamChoice(content)]


def test_streaming_cost_estimation(monkeypatch):
    """Streaming path estimates cost via token_counter + cost_per_token."""

    def mock_completion(*, model, messages, api_key, stream, **kwargs):
        assert stream is True
        return [MockStreamChunk("hello "), MockStreamChunk("world")]

    monkeypatch.setattr("core.model_adapter.litellm.completion", mock_completion)

    token_call_log: list[tuple[str, Any]] = []

    def mock_token_counter(*, model, messages=None, text=None):
        if messages is not None:
            token_call_log.append(("prompt", messages))
            return 10
        token_call_log.append(("completion", text))
        return 5

    monkeypatch.setattr("core.model_adapter.litellm.token_counter", mock_token_counter)

    def mock_cost_per_token(*, model, prompt_tokens, completion_tokens):
        return (prompt_tokens * 1e-5, completion_tokens * 2e-5)

    monkeypatch.setattr("core.model_adapter.litellm.cost_per_token", mock_cost_per_token)

    result = call_model(
        messages=[{"role": "user", "content": "test"}],
        config={"model": {"name": "gpt-4o", "api_key": "sk-test", "stream": True}},
    )
    assert isinstance(result, ModelResponse)
    assert result.cost == pytest.approx(10 * 1e-5 + 5 * 2e-5)
    assert result.message["content"] == "hello world"
    assert result.message["cost_calculation_method"] == "token_based"


def test_streaming_cost_missing_warn(monkeypatch):
    """Streaming cost estimation failure falls back to 0 with warn strategy."""

    def mock_completion(*, model, messages, api_key, stream, **kwargs):
        return [MockStreamChunk("hi")]

    monkeypatch.setattr("core.model_adapter.litellm.completion", mock_completion)

    def mock_token_counter(*, model, messages=None, text=None):
        raise RuntimeError("token counter failed")

    monkeypatch.setattr("core.model_adapter.litellm.token_counter", mock_token_counter)

    result = call_model(
        messages=[{"role": "user", "content": "test"}],
        config={
            "model": {
                "name": "gpt-4o",
                "api_key": "sk-test",
                "stream": True,
                "cost_missing_strategy": "warn",
            }
        },
    )
    assert result.cost == pytest.approx(0.0)
    assert result.message["cost_calculation_method"] == "missing"


def test_streaming_cost_missing_error(monkeypatch):
    """Streaming cost estimation failure raises CostMissingError with error strategy."""

    def mock_completion(*, model, messages, api_key, stream, **kwargs):
        return [MockStreamChunk("hi")]

    monkeypatch.setattr("core.model_adapter.litellm.completion", mock_completion)

    def mock_token_counter(*, model, messages=None, text=None):
        raise RuntimeError("token counter failed")

    monkeypatch.setattr("core.model_adapter.litellm.token_counter", mock_token_counter)

    with pytest.raises(CostMissingError):
        call_model(
            messages=[{"role": "user", "content": "test"}],
            config={
                "model": {
                    "name": "gpt-4o",
                    "api_key": "sk-test",
                    "stream": True,
                    "cost_missing_strategy": "error",
                }
            },
        )
