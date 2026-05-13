"""Parser: strict action extraction from model responses.

Supports two protocols:
  1. tool-call — exactly one bash tool_call in message["tool_calls"].
  2. text      — exactly one fence block ``...`` or XML block <...>.

Any deviation (0, 2+, mixed, empty command) raises FormatError.

Dependencies: re (stdlib), core.models.FormatError.
Test coverage: tests/unit/test_parser.py.
"""

from __future__ import annotations

import re
from typing import Any

from core.models import FormatError

# ── Regex for text-mode action blocks ─────────────────────────
_FENCE_RE = re.compile(
    r"```mswea_bash_command\n(.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)
_XML_RE = re.compile(
    r"<mswea_bash_command>(.*?)</mswea_bash_command>",
    re.DOTALL | re.IGNORECASE,
)


def _extract_fence_blocks(content: str) -> list[str]:
    """Extract fenced bash-command blocks."""
    return [m.group(1).strip() for m in _FENCE_RE.finditer(content)]


def _extract_xml_blocks(content: str) -> list[str]:
    """Extract XML bash-command blocks."""
    return [m.group(1).strip() for m in _XML_RE.finditer(content)]


def parse_action(message: dict[str, Any], protocol: str) -> str:
    """Extract the single executable action from *message*.

    Args:
        message: A dict representing the assistant's response.  Expected keys:
            ``tool_calls`` (list, optional) and ``content`` (str, optional).
        protocol: One of ``"tool-call"`` or ``"text"``.

    Returns:
        The extracted command string.

    Raises:
        FormatError: If the response does not contain *exactly one* valid action.
    """
    tool_calls = message.get("tool_calls") or []
    content = message.get("content", "")

    # Unified text-block extraction (performed up-front so we can detect
    # tool-call + text conflicts regardless of the requested protocol).
    fence_blocks = _extract_fence_blocks(content)
    xml_blocks = _extract_xml_blocks(content)
    text_blocks = fence_blocks + xml_blocks

    # ── Tool-call detection ───────────────────────────────────
    tool_call_count = len(tool_calls)
    if tool_call_count > 0:
        if tool_call_count == 1:
            tool_call = tool_calls[0]
            # We accept bash-type tool_calls
            if tool_call.get("type") == "bash":
                command = tool_call.get("function", {}).get("arguments", {}).get("command", "")
                if not command:
                    raise FormatError("Empty command", "empty_command")
                # Conflict: tool-call + text blocks simultaneously
                if text_blocks:
                    raise FormatError(
                        "Tool-call and text conflict",
                        "mixed_protocol",
                    )
                return command
        raise FormatError(
            f"Expected exactly 1 tool_call, got {tool_call_count}",
            "multiple_tool_calls",
        )

    # ── Text-mode detection ───────────────────────────────────
    if fence_blocks and xml_blocks:
        raise FormatError(
            "Fence and XML blocks conflict",
            "mixed_protocol",
        )

    if len(fence_blocks) == 1:
        cmd = fence_blocks[0]
        if not cmd:
            raise FormatError("Empty command", "empty_command")
        return cmd

    if len(xml_blocks) == 1:
        cmd = xml_blocks[0]
        if not cmd:
            raise FormatError("Empty command", "empty_command")
        return cmd

    raise FormatError(
        "Expected exactly 1 action block",
        "no_action",
    )
