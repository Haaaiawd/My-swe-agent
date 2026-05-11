"""Integration test for format-error anti-loop counter (CH-R4-01).

Reference: CHALLENGE_REPORT.md CH-R4-01, core-agent.detail.md §4.
Verifies that 5 consecutive FormatErrors transitions to UNKNOWN_ERROR.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from core.agent import Agent


def test_format_error_threshold_reaches_unknown_error(tmp_path: Path) -> None:
    """Given a model that always returns unparseable responses,
    When the agent runs,
    Then after max_consecutive_format_errors (default 5) it enters UNKNOWN_ERROR.
    """
    cfg = {
        "task_description": "test",
        "model": {"name": "mock", "protocol": "text"},
        "agent": {
            "step_limit": 20,
            "cost_limit": 10.0,
            "cost_estimate_per_call": 0.01,
            "max_consecutive_format_errors": 3,
        },
        "output": {"trajectory_path": str(tmp_path / "traj.jsonl")},
    }

    call_count = 0

    def always_bad(*args: Any, **kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        from core.models import ModelResponse

        return ModelResponse(
            message={"role": "assistant", "content": "not_a_valid_command"},
            cost=0.001,
        )

    with patch("core.state_machine.call_model", always_bad):
        agent = Agent(cfg)
        result = agent.run("test task")

    assert result.returncode == 6  # UNKNOWN_ERROR
    assert result.final_state == "UNKNOWN_ERROR"
    assert call_count >= 3  # At least threshold number of model calls
