"""Core Agent System — data models and enums.

Defines all domain primitives used by Parser, Executor, Observer, ModelAdapter,
TrajectoryManager, and the StateMachine.

Dependencies: dataclasses, datetime, enum, pathlib, typing.
Test coverage: tests/unit/test_models.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# ── Enums ───────────────────────────────────────────────────────


class State(str, Enum):
    """State-machine states (intermediate + terminal)."""

    MODEL = "MODEL"
    PARSE = "PARSE"
    CONFIRM = "CONFIRM"
    EXECUTE = "EXECUTE"
    OBSERVE = "OBSERVE"
    # Terminal states
    SUBMITTED = "SUBMITTED"
    LIMIT_STEP = "LIMIT_STEP"
    LIMIT_COST = "LIMIT_COST"
    INTERRUPT = "INTERRUPT"
    FATAL_CONFIG = "FATAL_CONFIG"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class Protocol(str, Enum):
    """Action-parsing protocol."""

    TOOL_CALL = "tool-call"
    TEXT = "text"


# ── Execution ───────────────────────────────────────────────────


@dataclass
class ExecutionResult:
    """Subprocess execution result.

    ``stdout`` may be truncated/observation-rendered; ``stdout_original``
    preserves the raw output for submission-marker detection (ADR-006).
    """

    returncode: int
    stdout: str
    stderr: str
    stdout_original: str | None = None
    exception_metadata: dict[str, Any] | None = None

    def is_success(self) -> bool:
        """Return ``True`` if the command exited with code 0."""
        return self.returncode == 0

    def get_output(self) -> str:
        """Return the combined stdout + stderr string."""
        if self.stderr:
            return f"{self.stdout}\n{self.stderr}"
        return self.stdout


# ── Observation ───────────────────────────────────────────────


@dataclass
class Observation:
    """Observer output: rendered content + optional submission."""

    content: str
    submitted: bool
    submission_text: str | None = None

    def has_submission(self) -> bool:
        """Return ``True`` if a submission was detected and extracted."""
        return self.submitted and self.submission_text is not None


# ── Model Response ──────────────────────────────────────────────


@dataclass
class ModelResponse:
    """LLM API response wrapper."""

    message: dict[str, Any]
    cost: float

    def is_tool_call(self) -> bool:
        """Return ``True`` if the response contains tool calls."""
        return "tool_calls" in self.message


# ── Trajectory ──────────────────────────────────────────────────


@dataclass
class Trajectory:
    """Execution trajectory record (schema v1_jsonl)."""

    schema_version: str = "v1"
    messages: list[dict[str, Any]] = field(default_factory=list)
    cost_accumulator: float = 0.0
    step_counter: int = 0

    def add_message(
        self,
        message: dict[str, Any],
        tool_call_id: str | None = None,
    ) -> None:
        """Append a message to the trajectory, optionally tagging *tool_call_id*."""
        msg = dict(message)
        # Some providers (e.g. Poolside) require tool_call_id on every tool
        # message; always set it, using empty string as fallback.
        if msg.get("role") == "tool" or tool_call_id is not None:
            msg["tool_call_id"] = tool_call_id or ""
        msg["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.messages.append(msg)

    def add_cost(self, cost: float) -> None:
        """Accumulate step cost into the running total."""
        self.cost_accumulator += cost

    def increment_step(self) -> None:
        """Increment the step counter.

        Step semantics: one step is counted each time a command execution
        completes (entering OBSERVE), regardless of returncode.  Steps are
        **not** counted when the command never executes (FormatError,
        CommandValidationError, timeout exceptions, etc.).
        """
        self.step_counter += 1


# ── State-Machine Context ───────────────────────────────────────


@dataclass
class StateMachineContext:
    """Mutable context shared across state-machine transitions."""

    response: ModelResponse | None = None
    command: str | None = None
    result: ExecutionResult | None = None
    observation: Observation | None = None
    tool_call_id: str | None = None
    consecutive_format_errors: int = 0  # CH-R4-01 anti-loop counter


# ── Exceptions ────────────────────────────────────────────────


class FormatError(Exception):
    """Raised when the model response does not contain exactly one action."""

    def __init__(self, message: str, error_type: str) -> None:
        super().__init__(message)
        self.message = message
        self.error_type = error_type


class CommandValidationError(Exception):
    """Raised when a parsed command fails safety validation."""

    def __init__(self, command: str, reason: str) -> None:
        super().__init__(f"Command validation failed: {reason}")
        self.command = command
        self.reason = reason


class CostMissingError(RuntimeError):
    """Raised when the API response lacks cost and strategy is *error*."""

    pass


# ── Agent Result ──────────────────────────────────────────────


@dataclass
class AgentResult:
    """Structured result returned by ``Agent.run()`` to the CLI layer."""

    trajectory_path: Path
    final_state: str  # one of State terminal values
    overall_output: str | None
    returncode: int
    model_name: str
    error: str | None = None
