"""ModelAdapter: LLM API calling via litellm with retry and cost tracking.

Supports tool-call and text response modes.  Retries up to 5 times on
transient litellm exceptions (Timeout, APIError, RateLimit,
ServiceUnavailable, APIConnectionError).  FormatError and AuthenticationError
are **not** retried (ADR-003).

Cost priority: API-provided cost → litellm token-based estimate → 0.
The ``cost_calculation_method`` field ("api" | "token_based" | "missing")
is appended to the returned message dict (ADR-007).

Dependencies: litellm, tenacity; core.models.CostMissingError, ModelResponse.
Test coverage: tests/unit/test_model_adapter.py (pytest-mock).
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import litellm
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.models import CostMissingError, ModelResponse

logger = logging.getLogger(__name__)

# Exceptions that warrant a retry (ADR-003)
_RETRY_EXCEPTIONS: tuple[type[Exception], ...] = (
    litellm.Timeout,
    litellm.APIError,
    litellm.RateLimitError,
    litellm.ServiceUnavailableError,
    litellm.APIConnectionError,
)

DEFAULT_SYSTEM_PROMPT = """\
You are mini-swe-agent, an autonomous programming task executor.
Your job is to solve the given task by executing bash commands one at a time.

RULES:
1. Output exactly ONE bash command per turn.
2. Wrap the command in the following format (no extra text outside):
   ```mswea_bash_command
   <your_command_here>
   ```
3. Do NOT output markdown explanations, tutorials, or any other text outside the fence block.
4. Do NOT output <tool_call> tags or other formats. Only the fence block above.
5. After the task is fully complete and verified, submit by outputting:
   COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
6. You will receive the command output (stdout/stderr) in the next
   message. Use it to plan your next step.
"""


def _inject_system_prompt(
    messages: list[dict[str, Any]],
    system_prompt: str | None,
) -> list[dict[str, Any]]:
    """Prepend a system message if not already present."""
    if not system_prompt:
        return messages
    # Avoid duplicate system message
    if messages and messages[0].get("role") == "system":
        return messages
    return [{"role": "system", "content": system_prompt}] + list(messages)


def _extract_message_dict(response: Any) -> dict[str, Any]:
    """Normalise a litellm response message to a plain dict."""
    msg = response.choices[0].message
    # Pydantic v2 / OpenAI object compatibility
    if hasattr(msg, "model_dump"):
        return dict(msg.model_dump())
    if hasattr(msg, "to_dict"):
        return dict(msg.to_dict())
    return dict(msg)


def _stream_completion(
    model_cfg: dict[str, Any],
    messages: list[dict[str, Any]],
) -> ModelResponse:
    """Call litellm with stream=True, print tokens live, assemble message."""
    response = litellm.completion(
        model=model_cfg.get("name", "gpt-4o"),
        messages=messages,
        api_key=model_cfg.get("api_key"),
        stream=True,
        **model_cfg.get("extra_params", {}),
    )

    # Collect streamed content and print live
    full_content = ""
    for chunk in response:
        delta = chunk.choices[0].delta
        token = delta.content or ""
        if token:
            sys.stdout.write(token)
            sys.stdout.flush()
            full_content += token

    # Streaming responses have no tool_calls; cost is unavailable
    return ModelResponse(
        message={"role": "assistant", "content": full_content},
        cost=0.0,
    )


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
    reraise=True,
)
def call_model(
    messages: list[dict[str, Any]],
    config: dict[str, Any],
) -> ModelResponse:
    """Call the LLM via litellm with retries and cost extraction.

    Args:
        messages: Conversation history (OpenAI-compatible message list).
        config: Merged configuration dict with ``model.*`` keys.

    Returns:
        ModelResponse with the assistant message and cost.

    Raises:
        CostMissingError: If the API response lacks cost info and
            ``cost_missing_strategy`` is ``"error"``.
        Exception: After 5 retry attempts on transient errors, the final
            exception is re-raised.
    """
    model_cfg = config.get("model", {})
    stream = model_cfg.get("stream", False)

    # Inject system prompt
    system_prompt = model_cfg.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
    messages = _inject_system_prompt(messages, system_prompt)

    # Streaming path
    if stream:
        return _stream_completion(model_cfg, messages)

    # Non-streaming path
    response = litellm.completion(
        model=model_cfg.get("name", "gpt-4o"),
        messages=messages,
        api_key=model_cfg.get("api_key"),
        **model_cfg.get("extra_params", {}),
    )

    # ── Cost extraction ───────────────────────────────────────
    cost: float | None = None
    cost_calculation_method = "api"

    # 1. Try API-reported cost (litellm internal attribute)
    cost = getattr(response, "_response_cost", None)

    # 2. Fallback: token-based estimation via litellm
    if cost is None:
        try:
            cost = litellm.completion_cost(response)
            cost_calculation_method = "token_based"
        except Exception:
            cost = None

    # 3. Final fallback: handle missing cost per strategy
    if cost is None:
        strategy = model_cfg.get("cost_missing_strategy", "warn")
        if strategy == "error":
            raise CostMissingError("Cost information missing from API response")
        if strategy == "warn":
            logger.warning("Cost missing from API response; using 0")
        cost = 0.0
        cost_calculation_method = "missing"

    # ── Message flattening ────────────────────────────────────
    message = _extract_message_dict(response)
    message["cost_calculation_method"] = cost_calculation_method

    return ModelResponse(message=message, cost=float(cost))
