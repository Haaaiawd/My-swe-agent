"""Integration tests for CLI run subcommand.

Reference: cli-system.detail.md §3.1, 05A_TASKS.md T3.1.2.
Coverage: normal path, ConfigError diagnostic file, --model override, exit code mapping.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from cli.exit_codes import EXIT_CODES
from core.models import AgentResult


@pytest.fixture
def minimal_config(tmp_path: Path) -> Path:
    """Write a minimal valid YAML config and return its path."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "task_description: 'write hello world'\n"
        "model:\n"
        "  name: gpt-4\n"
        "  protocol: text\n"
        "agent:\n"
        "  step_limit: 3\n"
        "  cost_limit: 1.0\n",
        encoding="utf-8",
    )
    return cfg


def _raising_exit(code: int) -> None:
    """Mock sys.exit that actually raises SystemExit so pytest can catch it."""
    raise SystemExit(code)


class FakeAgent:
    """Fake Agent class that returns a controlled AgentResult."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def run(self, task: str, step_callback=None, token_callback=None) -> AgentResult:
        return AgentResult(
            trajectory_path=Path("/tmp/traj.json"),
            final_state="SUBMITTED",
            overall_output="done",
            returncode=0,
            model_name=self.config.get("model", {}).get("name", "unknown"),
        )


def test_run_normal_path(minimal_config: Path, tmp_path: Path, monkeypatch: Any) -> None:
    """Given valid config and --yolo, run exits 0."""
    monkeypatch.setattr(sys, "exit", _raising_exit)

    with patch("cli.main.Agent", FakeAgent), pytest.raises(SystemExit) as exc_info:
        from cli.main import run_cmd

        run_cmd.callback(
            config_paths=(minimal_config,),
            model=None,
            yolo=True,
            step_limit=None,
            cost_limit=None,
            output=tmp_path / "outputs",
            verbose=False,
            task=None,
            exit_immediately=None,
        )

    assert exc_info.value.code == EXIT_CODES["SUCCESS"]


def test_run_config_error_writes_diagnostic(
    minimal_config: Path, tmp_path: Path, monkeypatch: Any
) -> None:
    """Given broken config, diagnostic JSON is written and exit code is 13."""
    monkeypatch.setattr(sys, "exit", _raising_exit)

    with patch("cli.main.ConfigManager") as mock_mgr, pytest.raises(SystemExit) as exc_info:
        mgr = mock_mgr.return_value
        from config import ConfigError

        mgr.load_config.side_effect = ConfigError(
            "bad yaml", file_path=str(minimal_config), line=2, variable="foo"
        )

        from cli.main import run_cmd

        output_dir = tmp_path / "outputs"
        run_cmd.callback(
            config_paths=(minimal_config,),
            model=None,
            yolo=True,
            step_limit=None,
            cost_limit=None,
            output=output_dir,
            verbose=False,
            task=None,
            exit_immediately=None,
        )

    assert exc_info.value.code == EXIT_CODES["AGENT_FATAL_CONFIG"]

    # Diagnostic file written (CH-R5-05: config_error_<timestamp>.txt)
    diag_files = list(output_dir.glob("config_error_*.txt"))
    assert len(diag_files) == 1
    diag = json.loads(diag_files[0].read_text(encoding="utf-8"))
    assert diag["error_type"] == "ConfigError"
    assert diag["message"] == "bad yaml"
    assert diag["file_path"] == str(minimal_config)
    assert diag["line"] == 2
    assert diag["variable"] == "foo"


def test_run_model_override(minimal_config: Path, tmp_path: Path, monkeypatch: Any) -> None:
    """--model overrides only model.name, preserving nested fields."""
    captured_config: dict[str, Any] | None = None

    class CaptureAgent(FakeAgent):
        def __init__(self, config: dict[str, Any]) -> None:
            nonlocal captured_config
            captured_config = config
            super().__init__(config)

    monkeypatch.setattr(sys, "exit", _raising_exit)

    with patch("cli.main.Agent", CaptureAgent), pytest.raises(SystemExit):
        from cli.main import run_cmd

        run_cmd.callback(
            config_paths=(minimal_config,),
            model="overridden-model",
            yolo=True,
            step_limit=None,
            cost_limit=None,
            output=tmp_path / "outputs",
            verbose=False,
            task=None,
            exit_immediately=None,
        )

    assert captured_config is not None
    assert captured_config["model"]["name"] == "overridden-model"
    assert captured_config["model"]["protocol"] == "text"  # preserved


def test_run_exit_code_mapping(minimal_config: Path, tmp_path: Path, monkeypatch: Any) -> None:
    """Core returncode 2 (LIMIT_STEP) maps to CLI exit code 10."""

    class LimitStepAgent(FakeAgent):
        def run(self, task: str, step_callback=None, token_callback=None) -> AgentResult:
            return AgentResult(
                trajectory_path=Path("/tmp/traj.json"),
                final_state="LIMIT_STEP",
                overall_output=None,
                returncode=2,
                model_name="gpt-4",
            )

    monkeypatch.setattr(sys, "exit", _raising_exit)

    with patch("cli.main.Agent", LimitStepAgent), pytest.raises(SystemExit) as exc_info:
        from cli.main import run_cmd

        run_cmd.callback(
            config_paths=(minimal_config,),
            model=None,
            yolo=True,
            step_limit=None,
            cost_limit=None,
            output=tmp_path / "outputs",
            verbose=False,
            task=None,
            exit_immediately=None,
        )

    assert exc_info.value.code == EXIT_CODES["AGENT_LIMIT_STEP"]
