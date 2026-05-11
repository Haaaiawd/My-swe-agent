"""Unit tests for core data structures.

Covers: State enum, Protocol enum, ExecutionResult, Observation, ModelResponse,
Trajectory, StateMachineContext, FormatError, CommandValidationError, CostMissingError,
AgentResult.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.models import (
    AgentResult,
    CommandValidationError,
    CostMissingError,
    ExecutionResult,
    FormatError,
    ModelResponse,
    Observation,
    Protocol,
    State,
    StateMachineContext,
    Trajectory,
)


class TestStateEnum:
    def test_terminal_states_exist(self):
        assert State.SUBMITTED == "SUBMITTED"
        assert State.LIMIT_STEP == "LIMIT_STEP"
        assert State.LIMIT_COST == "LIMIT_COST"
        assert State.INTERRUPT == "INTERRUPT"
        assert State.FATAL_CONFIG == "FATAL_CONFIG"
        assert State.UNKNOWN_ERROR == "UNKNOWN_ERROR"

    def test_intermediate_states_exist(self):
        assert State.MODEL == "MODEL"
        assert State.PARSE == "PARSE"
        assert State.EXECUTE == "EXECUTE"
        assert State.OBSERVE == "OBSERVE"


class TestProtocolEnum:
    def test_values(self):
        assert Protocol.TOOL_CALL == "tool-call"
        assert Protocol.TEXT == "text"


class TestExecutionResult:
    def test_success(self):
        result = ExecutionResult(returncode=0, stdout="hello", stderr="")
        assert result.is_success()

    def test_failure(self):
        result = ExecutionResult(returncode=1, stdout="", stderr="err")
        assert not result.is_success()

    def test_stdout_original_field(self):
        result = ExecutionResult(
            returncode=0, stdout="trunc", stderr="", stdout_original="original"
        )
        assert result.stdout_original == "original"

    def test_get_output_with_stderr(self):
        result = ExecutionResult(returncode=1, stdout="out", stderr="err")
        assert result.get_output() == "out\nerr"

    def test_get_output_no_stderr(self):
        result = ExecutionResult(returncode=0, stdout="out", stderr="")
        assert result.get_output() == "out"


class TestObservation:
    def test_has_submission_true(self):
        obs = Observation(content="ok", submitted=True, submission_text="patch")
        assert obs.has_submission()

    def test_has_submission_no_text(self):
        obs = Observation(content="ok", submitted=True, submission_text=None)
        assert not obs.has_submission()

    def test_has_submission_not_submitted(self):
        obs = Observation(content="ok", submitted=False, submission_text="patch")
        assert not obs.has_submission()


class TestModelResponse:
    def test_is_tool_call_true(self):
        resp = ModelResponse(message={"tool_calls": [{"id": "1"}]}, cost=0.01)
        assert resp.is_tool_call()

    def test_is_tool_call_false(self):
        resp = ModelResponse(message={"content": "hello"}, cost=0.01)
        assert not resp.is_tool_call()


class TestTrajectory:
    def test_add_message(self):
        traj = Trajectory()
        traj.add_message({"role": "user", "content": "hi"})
        assert len(traj.messages) == 1
        assert "timestamp" in traj.messages[0]

    def test_add_message_with_tool_call_id(self):
        traj = Trajectory()
        traj.add_message({"role": "tool", "content": "ok"}, tool_call_id="tc_1")
        assert traj.messages[0]["tool_call_id"] == "tc_1"

    def test_add_cost(self):
        traj = Trajectory()
        traj.add_cost(0.01)
        traj.add_cost(0.02)
        assert traj.cost_accumulator == pytest.approx(0.03)

    def test_increment_step(self):
        traj = Trajectory()
        traj.increment_step()
        assert traj.step_counter == 1

    def test_default_schema_version(self):
        traj = Trajectory()
        assert traj.schema_version == "v1"


class TestStateMachineContext:
    def test_format_error_counter_default(self):
        ctx = StateMachineContext()
        assert ctx.consecutive_format_errors == 0


class TestFormatError:
    def test_attributes(self):
        err = FormatError("bad", "no_tool_call")
        assert err.error_type == "no_tool_call"
        assert "bad" in str(err)


class TestCommandValidationError:
    def test_attributes(self):
        err = CommandValidationError("rm -rf /", "destructive")
        assert err.command == "rm -rf /"
        assert err.reason == "destructive"


class TestCostMissingError:
    def test_is_runtime_error(self):
        assert issubclass(CostMissingError, RuntimeError)


class TestAgentResult:
    def test_fields(self):
        result = AgentResult(
            trajectory_path=Path("/tmp/traj.json"),
            final_state="SUBMITTED",
            overall_output="patch",
            returncode=0,
            model_name="gpt-4o",
        )
        assert result.final_state == "SUBMITTED"
        assert result.returncode == 0
        assert result.overall_output == "patch"
