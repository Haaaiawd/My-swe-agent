"""StateMachine: core state-machine loop (MODEL → PARSE → (VALIDATE) → EXECUTE → OBSERVE).

The loop continues until a terminal state is reached.  Signal handlers
capture SIGINT / SIGTERM and transition to INTERRUPT.

Dependencies: signal, core.models, core.parser, core.executor,
core.validator, core.observer, core.model_adapter, core.trajectory.
"""

from __future__ import annotations

import logging
import signal
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jinja2

from config.renderer import DEFAULT_MAX_OBSERVATION_LENGTH, TemplateRenderer
from core.executor import execute_command
from core.model_adapter import call_model
from core.models import (
    AgentResult,
    State,
    StateMachineContext,
    Trajectory,
)
from core.observer import observe_result
from core.parser import parse_action
from core.trajectory import TrajectoryManager
from core.validator import validate_command

logger = logging.getLogger(__name__)

TERMINAL_STATES = {
    State.SUBMITTED,
    State.LIMIT_STEP,
    State.LIMIT_COST,
    State.INTERRUPT,
    State.FATAL_CONFIG,
    State.UNKNOWN_ERROR,
}

# Core → CLI returncode mapping (ADR-006)
EXITCODE_MAP: dict[State, int] = {
    State.SUBMITTED: 0,
    State.LIMIT_STEP: 2,
    State.LIMIT_COST: 3,
    State.INTERRUPT: 4,
    State.FATAL_CONFIG: 5,
    State.UNKNOWN_ERROR: 6,
}


class StateMachine:
    """Core agent state machine."""

    def __init__(
        self,
        config: dict[str, Any],
        confirm_callback: Callable[[str], bool] | None = None,
    ) -> None:
        self.config = config
        self.confirm_callback = confirm_callback
        self._interrupted = False
        self._obs_renderer = TemplateRenderer(
            jinja2.Environment(
                undefined=jinja2.StrictUndefined,
                trim_blocks=True,
                lstrip_blocks=True,
            )
        )
        self._setup_signal_handlers()

    # ── Signal handling ───────────────────────────────────────

    def _setup_signal_handlers(self) -> None:
        """Register SIGINT / SIGTERM handlers (best-effort on all platforms)."""
        try:
            signal.signal(signal.SIGINT, self._on_interrupt)
            signal.signal(signal.SIGTERM, self._on_interrupt)
        except (ValueError, OSError):
            # Platform may not support full signal semantics (e.g. Windows spawn)
            pass

    def _on_interrupt(self, _signum: int, _frame: Any) -> None:
        logger.warning("Received interrupt signal")
        self._interrupted = True

    # ── Main loop ───────────────────────────────────────────

    def run(self, task: str) -> AgentResult:
        """Execute the state-machine loop for *task* and return the result."""
        state = State.MODEL
        trajectory = Trajectory()
        trajectory.add_message({"role": "user", "content": task})
        ctx = StateMachineContext()
        traj_mgr = TrajectoryManager(trajectory)

        while state not in TERMINAL_STATES:
            # External interrupt check
            if self._interrupted:
                state = State.INTERRUPT
                continue

            try:
                state = self._step(state, ctx, traj_mgr)
            except Exception as exc:
                logger.exception("Unexpected error in state machine: %s", exc)
                state = State.UNKNOWN_ERROR

        # Save trajectory before returning (best-effort)
        traj_path = self.config.get("output", {}).get("trajectory_path")
        if traj_path:
            try:
                traj_mgr.save_trajectory(traj_path, final_state=state.value)
            except OSError:
                logger.exception("Failed to save trajectory")

        returncode = EXITCODE_MAP.get(state, 6)
        return AgentResult(
            trajectory_path=Path(str(traj_path or "")),
            final_state=state.value,
            overall_output=self._extract_overall_output(trajectory)
            if state == State.SUBMITTED
            else None,
            returncode=returncode,
            model_name=self.config.get("model", {}).get("name", "unknown"),
            error=None if state == State.SUBMITTED else state.value,
        )

    # ── Per-state handlers ──────────────────────────────────

    def _step(self, state: State, ctx: StateMachineContext, traj_mgr: TrajectoryManager) -> State:
        """Execute a single state transition."""
        cfg = self.config
        agent_cfg = cfg.get("agent", {})
        model_cfg = cfg.get("model", {})
        step_limit = agent_cfg.get("step_limit", 50)
        cost_limit = agent_cfg.get("cost_limit", 2.0)
        cost_estimate = agent_cfg.get("cost_estimate_per_call", 0.05)
        timeout = cfg.get("executor", {}).get("timeout", 120)
        protocol = model_cfg.get("protocol", "tool-call")

        if state == State.MODEL:
            # Preventive cost check (CH-R3-09)
            if traj_mgr.trajectory.cost_accumulator + cost_estimate > cost_limit:
                return State.LIMIT_COST

            ctx.response = call_model(traj_mgr.trajectory.messages, cfg)
            traj_mgr.trajectory.add_cost(ctx.response.cost)

            # Extract tool_call_id for tool-call mode
            if ctx.response.is_tool_call():
                tool_calls = ctx.response.message.get("tool_calls", [])
                if tool_calls:
                    ctx.tool_call_id = tool_calls[0].get("id")

            traj_mgr.append(ctx.response.message)
            return State.PARSE

        if state == State.PARSE:
            try:
                command = parse_action(ctx.response.message, protocol)
            except Exception as exc:
                # FormatError (or any parse failure)
                ctx.consecutive_format_errors += 1
                traj_mgr.append(
                    {"role": "system", "content": f"Parse error: {exc}"}, ctx.tool_call_id
                )
                ctx.tool_call_id = None

                max_err = agent_cfg.get("max_consecutive_format_errors", 5)
                if ctx.consecutive_format_errors >= max_err:
                    logger.error(
                        "FormatError threshold reached (%s), entering UNKNOWN_ERROR", max_err
                    )
                    return State.UNKNOWN_ERROR
                return State.MODEL

            # Reset anti-loop counter on successful parse
            ctx.consecutive_format_errors = 0
            ctx.command = command

            # VALIDATE sub-step (CH-R4-02)
            try:
                validate_command(ctx.command)
            except Exception as exc:
                traj_mgr.append(
                    {"role": "system", "content": f"Validation error: {exc}"}, ctx.tool_call_id
                )
                ctx.tool_call_id = None
                return State.MODEL

            return State.CONFIRM

        if state == State.CONFIRM:
            confirm_mode = agent_cfg.get("confirm_mode", True)
            if (
                confirm_mode
                and self.confirm_callback is not None
                and not self.confirm_callback(ctx.command)
            ):
                logger.warning("User declined command execution")
                return State.INTERRUPT
            return State.EXECUTE

        if state == State.EXECUTE:
            ctx.result = execute_command(ctx.command, timeout=timeout)
            return State.OBSERVE

        if state == State.OBSERVE:
            ctx.observation = observe_result(ctx.result, cfg, template_renderer=self._obs_renderer)

            # Enforce observation length cap
            max_len = cfg.get("output", {}).get(
                "observation_max_length", DEFAULT_MAX_OBSERVATION_LENGTH
            )
            if len(ctx.observation.content) > max_len:
                ctx.observation.content = self._obs_renderer.truncate(
                    ctx.observation.content, max_len
                )

            traj_mgr.append(
                {"role": "tool", "content": ctx.observation.content},
                ctx.tool_call_id,
            )
            ctx.tool_call_id = None

            if ctx.observation.has_submission():
                return State.SUBMITTED

            # Check limits
            if traj_mgr.trajectory.step_counter >= step_limit:
                return State.LIMIT_STEP
            if traj_mgr.trajectory.cost_accumulator >= cost_limit:
                return State.LIMIT_COST

            return State.MODEL

        # Should never reach here for non-terminal states
        logger.error("Unexpected state: %s", state)
        return State.UNKNOWN_ERROR

    # ── Helpers ─────────────────────────────────────────────

    @staticmethod
    def _extract_overall_output(trajectory: Trajectory) -> str | None:
        """Extract the overall submission text from the trajectory."""
        for msg in reversed(trajectory.messages):
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                lines = content.splitlines()
                if lines and lines[0].strip() == "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT":
                    return "\n".join(lines[1:]) if len(lines) > 1 else ""
        return None
