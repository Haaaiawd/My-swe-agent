"""Unit tests for CLI exit code mapping.

Reference: cli-system.detail.md §1 EXIT_CODES, core-agent.detail.md §1 State enum.
Coverage: all 6 Core agent terminal states + unknown fallback.
"""

import pytest

from cli.exit_codes import EXIT_CODES, map_agent_result_to_exit_code


@pytest.mark.parametrize(
    "agent_rc,expected_cli",
    [
        (0, EXIT_CODES["SUCCESS"]),  # SUBMITTED
        (2, EXIT_CODES["AGENT_LIMIT_STEP"]),  # LIMIT_STEP
        (3, EXIT_CODES["AGENT_LIMIT_COST"]),  # LIMIT_COST
        (4, EXIT_CODES["AGENT_INTERRUPT"]),  # INTERRUPT
        (5, EXIT_CODES["AGENT_FATAL_CONFIG"]),  # FATAL_CONFIG
        (6, EXIT_CODES["AGENT_UNKNOWN_ERROR"]),  # UNKNOWN_ERROR
    ],
)
def test_map_agent_result_known_states(agent_rc: int, expected_cli: int) -> None:
    assert map_agent_result_to_exit_code(agent_rc) == expected_cli


def test_map_agent_result_unknown_fallback() -> None:
    """Unknown returncodes map to AGENT_UNKNOWN_ERROR."""
    assert map_agent_result_to_exit_code(99) == EXIT_CODES["AGENT_UNKNOWN_ERROR"]
    assert map_agent_result_to_exit_code(-1) == EXIT_CODES["AGENT_UNKNOWN_ERROR"]
