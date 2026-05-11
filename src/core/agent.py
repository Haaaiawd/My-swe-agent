"""Agent: top-level entry-point for the Core Agent System.

Thin wrapper around ``StateMachine``; kept as a separate layer so future
extensions (e.g. multi-run orchestration, pre/post hooks) can attach here
without touching the state-machine internals.

Dependencies: core.state_machine.StateMachine, core.models.AgentResult.
"""

from __future__ import annotations

from typing import Any

from core.models import AgentResult
from core.state_machine import StateMachine


class Agent:
    """Public API for running a single task through the agent loop."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def run(self, task: str) -> AgentResult:
        """Run *task* and return the structured result."""
        machine = StateMachine(self.config)
        return machine.run(task)
