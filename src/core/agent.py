"""Agent: top-level entry-point for the Core Agent System.

Thin wrapper around ``StateMachine``; kept as a separate layer so future
extensions (e.g. multi-run orchestration, pre/post hooks) can attach here
without touching the state-machine internals.

Dependencies: core.state_machine.StateMachine, core.models.AgentResult.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.models import AgentResult
from core.state_machine import StateMachine


class Agent:
    """Public API for running a single task through the agent loop."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def run(
        self,
        task: str,
        confirm_callback: Callable[[str], bool] | None = None,
        step_callback: Callable[[int, str, float], None] | None = None,
        token_callback: Callable[[str], None] | None = None,
    ) -> AgentResult:
        """Run *task* and return the structured result.

        Args:
            confirm_callback: Optional callable invoked per-step with the
                parsed command string.  Should return ``True`` to proceed to
                execution, ``False`` to interrupt.
            step_callback: Optional callable invoked after each executed step
                with ``(step_number, command, cumulative_cost)``.  Used by the
                CLI live progress panel.
            token_callback: Optional callable invoked per streamed token.
                When provided, tokens are NOT written to stdout.
        """
        machine = StateMachine(
            self.config,
            confirm_callback=confirm_callback,
            step_callback=step_callback,
            token_callback=token_callback,
        )
        return machine.run(task)
