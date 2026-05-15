"""Unit tests for the Textual trajectory checker step extraction.

Covers: cost extraction from message metadata, status mapping,
ANSI stripping, NUL replacement.
"""

from __future__ import annotations

import pytest

from cli.checker import _extract_steps


def test_extract_steps_reads_cost_from_message():
    """Assistant messages with 'cost' metadata should surface in steps."""
    data = {
        "messages": [
            {"role": "assistant", "content": "ls -la", "cost": 0.0123},
            {"role": "tool", "content": "file1.txt\nfile2.txt"},
            {"role": "assistant", "content": "cat file1.txt", "cost": 0.0087},
            {"role": "system", "content": "Parse error: malformed"},
        ]
    }
    steps = _extract_steps(data)
    assert len(steps) == 3  # 2 assistant + 1 system

    # First assistant step (status overwritten by following OK tool message)
    assert steps[0]["step_index"] == 1
    assert steps[0]["action"] == "ls -la"
    assert steps[0]["status"] == "OK"
    assert steps[0]["cost"] == pytest.approx(0.0123)

    # Second assistant step (no following tool/system → keeps MODEL)
    assert steps[1]["step_index"] == 2
    assert steps[1]["action"] == "cat file1.txt"
    assert steps[1]["status"] == "MODEL"
    assert steps[1]["cost"] == pytest.approx(0.0087)

    # System step (no cost metadata → defaults to 0.0)
    assert steps[2]["step_index"] == 3
    assert steps[2]["status"] == "FormatError"
    assert steps[2]["cost"] == 0.0


def test_extract_steps_status_mapping():
    """Tool/system messages should update the previous step's status."""
    data = {
        "messages": [
            {"role": "assistant", "content": "cmd"},
            {"role": "tool", "content": "Validation error: not allowed"},
        ]
    }
    steps = _extract_steps(data)
    assert len(steps) == 1
    assert steps[0]["status"] == "ValidationError"


def test_extract_steps_ansi_and_nul_cleaning():
    """ANSI sequences and NUL characters should be cleaned from actions."""
    data = {
        "messages": [
            {"role": "assistant", "content": "\x1b[31mred\x1b[0m\x00"},
        ]
    }
    steps = _extract_steps(data)
    assert steps[0]["action"] == "red␀"
