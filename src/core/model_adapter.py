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

ABSOLUTE RULES — VIOLATING ANY OF THESE IS A FAILURE:
1. You have ONLY ONE tool: the bash shell. No write_file(), no read_file(),
   no <tool_call>, no <function_call>, no other function names.
2. Every turn you output exactly ONE bash command.
3. Wrap the command ONLY in this format (no text before or after):
   ```mswea_bash_command
   <your_command_here>
   ```
4. Do NOT explain, do NOT use markdown outside the fence block,
   do NOT use <tool_call>, do NOT use XML tags.
5. After the task is fully complete and verified, submit by outputting:
   COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
6. You will receive the command output (stdout/stderr) in the next
   message. Use it to plan your next step.
"""


def _inject_system_prompt(
    messages: list[dict[str, Any]],
    system_prompt: str | None,
) -> list[dict[str, Any]]:
    """Inject system prompt as a standalone system message AND into first user.

    We do both: prepend a ``role="system"`` message (works for most providers)
    AND merge into the first user message (fallback for models that ignore
    standalone system messages).  This maximises the chance the instructions
    are actually seen.
    """
    if not system_prompt:
        return messages

    result: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    injected = False
    for msg in messages:
        if not injected and msg.get("role") == "user":
            content = msg.get("content", "")
            msg = {**msg, "content": f"{system_prompt}\n\n--- TASK ---\n\n{content}"}
            injected = True
        result.append(msg)
    return result


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
    """Call litellm with stream=True, print tokens live, assemble message.

    Cost is estimated via litellm.token_counter() + cost_per_token()
    because streaming responses do not include API-reported usage stats.
    """
    model_name = model_cfg.get("name", "gpt-4o")
    response = litellm.completion(
        model=model_name,
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

    # Estimate cost via token counter (streaming lacks API usage stats)
    cost = 0.0
    cost_calculation_method = "missing"
    try:
        prompt_tokens = litellm.token_counter(model=model_name, messages=messages)
        completion_tokens = litellm.token_counter(model=model_name, text=full_content)
        prompt_cost, completion_cost = litellm.cost_per_token(
            model=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        cost = prompt_cost + completion_cost
        cost_calculation_method = "token_based"
    except Exception as exc:
        strategy = model_cfg.get("cost_missing_strategy", "warn")
        if strategy == "error":
            raise CostMissingError(f"Cost estimation failed for streaming: {exc}") from exc
        if strategy == "warn":
            logger.warning("Streaming cost estimation failed: %s", exc)

    return ModelResponse(
        message={
            "role": "assistant",
            "content": full_content,
            "cost_calculation_method": cost_calculation_method,
        },
        cost=cost,
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

    # CH-R5-03: log structure at INFO, content only at DEBUG
    logger.info("[call_model] sending %d messages -> %s", len(messages), model_cfg.get("name"))
    for i, m in enumerate(messages):
        role = m.get("role", "?")
        content = str(m.get("content", ""))
        logger.info("  msg[%d] role=%s len=%d", i, role, len(content))
        logger.debug("  msg[%d] content preview: %s", i, content[:120].replace("\n", " "))

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
