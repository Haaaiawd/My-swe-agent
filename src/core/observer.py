"""Observer: result observation + submission-marker detection.

Detects the submission marker ``COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`` in
*stdout_original* (after ANSI-stripping, Unicode normalization, lstrip,
first-line match) only when returncode == 0 (ADR-006).

Renders the observation through an optional template renderer; on failure
falls back to ``stdout_original or stdout`` so the state machine can continue
(CH-R3-06).

Dependencies: unicodedata, re; core.models.ExecutionResult, Observation.
Test coverage: tests/unit/test_observer.py.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

from core.models import ExecutionResult, Observation

logger = logging.getLogger(__name__)

SUBMISSION_MARKER = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"

# ANSI escape sequence stripper
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from *text*."""
    return _ANSI_RE.sub("", text)


def _normalize(text: str) -> str:
    """Unicode-normalize (NFC) and lstrip *text*."""
    return unicodedata.normalize("NFC", text).lstrip()


def observe_result(
    execution_result: ExecutionResult,
    config: dict[str, Any],
    template_renderer: Any | None = None,
) -> Observation:
    """Observe *execution_result* and detect submission markers.

    Args:
        execution_result: The subprocess execution result.
        config: Merged configuration dict.
        template_renderer: Optional object with a ``render(template, context)``
            method (e.g. a ConfigManager or TemplateRenderer instance).

    Returns:
        An Observation containing the rendered content and optional submission.
    """
    submitted = False
    submission_text: str | None = None

    # Submission-marker detection (ADR-006): based on stdout_original,
    # only when returncode == 0.
    if execution_result.is_success():
        raw = execution_result.stdout_original or execution_result.stdout or ""
        cleaned = _normalize(_strip_ansi(raw))
        lines = cleaned.splitlines()
        if lines:
            # Strip surrounding quotes that shells add when model writes
            # echo 'MARKER' or echo "MARKER" — the quotes end up in stdout.
            first = lines[0].strip().strip("'\"")
            if first == SUBMISSION_MARKER:
                submitted = True
                # submission_text may be empty string (no extra lines) — that's fine;
                # use None only when marker itself is absent, not when output is empty.
                submission_text = "\n".join(lines[1:]) if len(lines) > 1 else ""

    # Observation template rendering (with fallback per CH-R3-06)
    if template_renderer is not None:
        try:
            context = {
                "stdout": execution_result.stdout,
                "stderr": execution_result.stderr,
                "returncode": execution_result.returncode,
            }
            content = template_renderer.render(
                config.get("observation_template", "{{ stdout }}"),
                context,
            )
        except Exception as e:
            logger.warning("Observation template render failed: %s. Falling back to raw output.", e)
            content = execution_result.stdout_original or execution_result.stdout or ""
    else:
        # Always include returncode; include stderr when present
        parts: list[str] = []
        if execution_result.stdout:
            parts.append(execution_result.stdout)
        if execution_result.stderr:
            parts.append(f"[stderr] {execution_result.stderr}")
        parts.append(f"[returncode={execution_result.returncode}]")
        content = "\n".join(parts)

    return Observation(
        content=content,
        submitted=submitted,
        submission_text=submission_text,
    )
