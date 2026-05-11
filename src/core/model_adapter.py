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


def _extract_message_dict(response: Any) -> dict[str, Any]:
    """Normalise a litellm response message to a plain dict."""
    msg = response.choices[0].message
    # Pydantic v2 / OpenAI object compatibility
    if hasattr(msg, "model_dump"):
        return dict(msg.model_dump())
    if hasattr(msg, "to_dict"):
        return dict(msg.to_dict())
    return dict(msg)


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
