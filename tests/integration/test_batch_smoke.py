"""Smoke test for batch processing preds.json schema.

Reference: cli-system.detail.md §3.2, ADR-002 §冒烟测试, 05A_TASKS.md T3.1.3.
Coverage: preds.json schema structure after batch run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from cli.batch import (
    BatchConfig,
    _load_instances,
    _write_preds_json,
    batch_run,
)
from cli.exit_codes import EXIT_CODES
from core.models import AgentResult


def test_load_instances(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    instance_file = dataset / "instance.jsonl"
    instance_file.write_text(
        json.dumps({"instance_id": "a", "task_description": "t1"})
        + "\n"
        + json.dumps({"instance_id": "b", "task_description": "t2"})
        + "\n",
        encoding="utf-8",
    )
    instances = _load_instances(dataset)
    assert len(instances) == 2
    assert instances[0]["instance_id"] == "a"


def test_write_preds_json_schema(tmp_path: Path) -> None:
    """ADR-002 P0: preds.json must contain instance_id, model_name_or_path, model_patch."""
    from cli.batch import BatchResult, PredEntry

    result = BatchResult(
        preds=[
            PredEntry(
                instance_id="django__1234",
                model_name_or_path="gpt-4",
                model_patch="patch diff",
            )
        ],
        output_path=tmp_path / "preds.json",
    )
    _write_preds_json(result)

    data = json.loads((tmp_path / "preds.json").read_text(encoding="utf-8"))
    assert "schema_version" in data
    assert "predictions" in data
    assert len(data["predictions"]) == 1
    pred = data["predictions"][0]
    assert "instance_id" in pred
    assert "model_name_or_path" in pred
    assert "model_patch" in pred


def test_batch_run_smoke(tmp_path: Path, monkeypatch: Any) -> None:
    """End-to-end batch smoke with mocked Agent."""
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    instance_file = dataset / "instance.jsonl"
    instance_file.write_text(
        json.dumps({"instance_id": "test_1", "task_description": "hello"}) + "\n",
        encoding="utf-8",
    )

    global_cfg = tmp_path / "config.yaml"
    global_cfg.write_text(
        "task_description: ''\n"
        "model:\n  name: gpt-4\n  protocol: text\n"
        "agent:\n  step_limit: 3\n  cost_limit: 1.0\n",
        encoding="utf-8",
    )

    class FakeAgent:
        def __init__(self, config: dict[str, Any]) -> None:
            pass

        def run(self, task: str) -> AgentResult:
            return AgentResult(
                trajectory_path=Path("/tmp/trajectory_test_1.jsonl"),
                final_state="SUBMITTED",
                overall_output="patch",
                returncode=0,
                model_name="gpt-4",
            )

    # Mock ProcessPoolExecutor to run inline (Windows spawn mode cannot see FakeAgent)
    from concurrent.futures import Future

    class InlineExecutor:
        def __init__(self, max_workers: int) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def submit(self, fn, *args, **kwargs):
            fut = Future()
            try:
                fut.set_result(fn(*args, **kwargs))
            except Exception as e:
                fut.set_exception(e)
            return fut

    with (
        patch("cli.batch.ProcessPoolExecutor", InlineExecutor),
        patch("cli.batch.Agent", FakeAgent),
    ):
        exit_code = batch_run(
            BatchConfig(
                dataset_path=dataset,
                global_config_path=global_cfg,
                workers=1,
                output_path=tmp_path / "preds.json",
                output_dir=tmp_path / "outputs",
            )
        )

    assert exit_code == EXIT_CODES["SUCCESS"]

    # Verify preds.json
    preds_data = json.loads((tmp_path / "preds.json").read_text(encoding="utf-8"))
    assert len(preds_data["predictions"]) == 1
    assert preds_data["predictions"][0]["instance_id"] == "test_1"
