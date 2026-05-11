"""Integration tests for the Core Agent state machine.

Uses monkeypatch to mock litellm/model responses; no real API calls.
Covers: happy-path loop, FormatError anti-loop, SUBMITTED, LIMIT_STEP.
"""

from __future__ import annotations

from core.agent import Agent
from core.models import AgentResult


class MockModelResponse:
    def __init__(
        self, content: str = "", tool_calls: list | None = None, cost: float = 0.01
    ) -> None:
        self.message = {
            "role": "assistant",
            "content": content,
            "tool_calls": tool_calls or [],
        }
        self.cost = cost

    def is_tool_call(self) -> bool:
        return bool(self.message.get("tool_calls"))


def _mock_call_model_echo_happy(messages, config):
    """Return a tool-call response with ``echo hello``."""
    return MockModelResponse(
        tool_calls=[
            {"id": "tc_1", "type": "bash", "function": {"arguments": {"command": "echo hello"}}}
        ],
        cost=0.01,
    )


def _mock_call_model_submission(messages, config):
    """Return a text-mode action (any action — we mock the executor)."""
    return MockModelResponse(
        content="```mswea_bash_command\necho hello\n```",
        cost=0.01,
    )


def _mock_call_model_format_error(messages, config):
    """Return a response with no action (triggers FormatError)."""
    return MockModelResponse(content="no action here", cost=0.0)


class TestStateMachineHappyPath:
    def test_echo_hello_closed_loop(self, monkeypatch, tmp_path):
        monkeypatch.setattr("core.state_machine.call_model", _mock_call_model_echo_happy)

        agent = Agent(
            config={
                "model": {"name": "gpt-4o", "protocol": "tool_call"},
                "agent": {"step_limit": 10, "cost_limit": 10.0, "max_consecutive_format_errors": 5},
                "executor": {"timeout": 10},
                "output": {"trajectory_path": str(tmp_path / "traj.json")},
            }
        )
        result = agent.run("say hello")
        assert isinstance(result, AgentResult)
        assert result.final_state == "SUBMITTED" or result.final_state in {
            "LIMIT_STEP",
            "LIMIT_COST",
            "INTERRUPT",
        }

    def test_submission_detection(self, monkeypatch, tmp_path):
        from core.models import ExecutionResult

        monkeypatch.setattr("core.state_machine.call_model", _mock_call_model_submission)

        def mock_execute(cmd, timeout):
            return ExecutionResult(
                returncode=0,
                stdout="COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\nmy patch\n",
                stderr="",
                stdout_original="COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\nmy patch\n",
            )

        monkeypatch.setattr("core.state_machine.execute_command", mock_execute)

        agent = Agent(
            config={
                "model": {"name": "gpt-4o", "protocol": "text"},
                "agent": {"step_limit": 10, "cost_limit": 10.0, "max_consecutive_format_errors": 5},
                "executor": {"timeout": 10},
                "output": {"trajectory_path": str(tmp_path / "traj.json")},
            }
        )
        result = agent.run("submit patch")
        assert result.final_state == "SUBMITTED"
        assert result.returncode == 0
        assert result.overall_output == "my patch"


class TestStateMachineErrorPaths:
    def test_format_error_loop(self, monkeypatch, tmp_path):
        monkeypatch.setattr("core.state_machine.call_model", _mock_call_model_format_error)

        agent = Agent(
            config={
                "model": {"name": "gpt-4o", "protocol": "text"},
                "agent": {"step_limit": 10, "cost_limit": 10.0, "max_consecutive_format_errors": 3},
                "executor": {"timeout": 10},
                "output": {"trajectory_path": str(tmp_path / "traj.json")},
            }
        )
        result = agent.run("loop test")
        assert result.final_state == "UNKNOWN_ERROR"
        assert result.returncode == 6

    def test_step_limit(self, monkeypatch, tmp_path):
        call_count = 0

        def mock_model(messages, config):
            nonlocal call_count
            call_count += 1
            return MockModelResponse(
                tool_calls=[
                    {
                        "id": f"tc_{call_count}",
                        "type": "bash",
                        "function": {"arguments": {"command": "echo step"}},
                    }
                ],
                cost=0.01,
            )

        monkeypatch.setattr("core.state_machine.call_model", mock_model)

        agent = Agent(
            config={
                "model": {"name": "gpt-4o", "protocol": "tool_call"},
                "agent": {"step_limit": 2, "cost_limit": 10.0, "max_consecutive_format_errors": 5},
                "executor": {"timeout": 10},
                "output": {"trajectory_path": str(tmp_path / "traj.json")},
            }
        )
        result = agent.run("step limit test")
        assert result.final_state == "LIMIT_STEP"
        assert result.returncode == 2
