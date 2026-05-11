"""CLI exit code mapping: CLI layer EXIT_CODES vs Core Agent returncode.

Core Agent returncode:
  0=SUBMITTED, 2=LIMIT_STEP, 3=LIMIT_COST, 4=INTERRUPT,
  5=FATAL_CONFIG, 6=UNKNOWN_ERROR

CLI EXIT_CODES:
  0=SUCCESS, 2=CLI_ERROR (click BadParameter), 10=AGENT_LIMIT_STEP,
  11=AGENT_LIMIT_COST, 12=AGENT_INTERRUPT, 13=AGENT_FATAL_CONFIG,
  14=AGENT_UNKNOWN_ERROR, 20=BATCH_PARTIAL_FAILURE, 21=USER_DECLINED,
  130=INTERRUPTED

Reference: cli-system.detail.md §1 EXIT_CODES, core-agent.detail.md §1 State enum.
Test coverage: tests/unit/test_exit_codes.py
"""

from __future__ import annotations

EXIT_CODES = {
    "SUCCESS": 0,
    "CLI_ERROR": 2,
    "AGENT_LIMIT_STEP": 10,
    "AGENT_LIMIT_COST": 11,
    "AGENT_INTERRUPT": 12,
    "AGENT_FATAL_CONFIG": 13,
    "AGENT_UNKNOWN_ERROR": 14,
    "BATCH_PARTIAL_FAILURE": 20,
    "USER_DECLINED": 21,
    "INTERRUPTED": 130,
}

_AGENT_TO_CLI_EXITCODE: dict[int, int] = {
    0: EXIT_CODES["SUCCESS"],  # SUBMITTED
    2: EXIT_CODES["AGENT_LIMIT_STEP"],  # LIMIT_STEP
    3: EXIT_CODES["AGENT_LIMIT_COST"],  # LIMIT_COST
    4: EXIT_CODES["AGENT_INTERRUPT"],  # INTERRUPT
    5: EXIT_CODES["AGENT_FATAL_CONFIG"],  # FATAL_CONFIG
    6: EXIT_CODES["AGENT_UNKNOWN_ERROR"],  # UNKNOWN_ERROR
}


def map_agent_result_to_exit_code(returncode: int) -> int:
    """Map a Core Agent returncode to a CLI exit code.

    Args:
        returncode: Core Agent returncode (0, 2, 3, 4, 5, 6).

    Returns:
        Corresponding CLI exit code from EXIT_CODES.
        Falls back to AGENT_UNKNOWN_ERROR for unrecognised returncodes.
    """
    return _AGENT_TO_CLI_EXITCODE.get(returncode, EXIT_CODES["AGENT_UNKNOWN_ERROR"])
