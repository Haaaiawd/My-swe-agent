"""Unit tests for batch processing components.

Reference: cli-system.detail.md §2.1, §2.2, 05A_TASKS.md T3.1.3.
Coverage: BatchConfig validation, PredEntry schema, should_run_instance logic.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

from cli.batch import (
    BatchConfig,
    BatchResult,
    PredEntry,
    _should_run_instance,
)


class TestBatchConfig:
    def test_defaults(self, tmp_path: Path) -> None:
        bc = BatchConfig(
            dataset_path=tmp_path,
            global_config_path=tmp_path / "cfg.yaml",
        )
        assert bc.workers >= 1
        assert bc.output_path == Path("./preds.json").resolve()
        assert bc.output_dir == Path("./outputs").resolve()

    def test_workers_cap_warning(self, tmp_path: Path) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            bc = BatchConfig(
                dataset_path=tmp_path,
                global_config_path=tmp_path / "cfg.yaml",
                workers=100,
            )
            assert bc.workers == 64
            assert len(w) == 1
            assert "capped" in str(w[0].message)

    def test_workers_negative(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="workers must be >= 1"):
            BatchConfig(
                dataset_path=tmp_path,
                global_config_path=tmp_path / "cfg.yaml",
                workers=0,
            )

    def test_slice_range_validation(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="slice_range start must be < stop"):
            BatchConfig(
                dataset_path=tmp_path,
                global_config_path=tmp_path / "cfg.yaml",
                slice_range=(5, 3),
            )

        with pytest.raises(ValueError, match="non-negative"):
            BatchConfig(
                dataset_path=tmp_path,
                global_config_path=tmp_path / "cfg.yaml",
                slice_range=(-1, 3),
            )


class TestPredEntry:
    def test_to_dict_schema(self) -> None:
        entry = PredEntry(
            instance_id="django__1234",
            model_name_or_path="gpt-4",
            model_patch="diff content",
        )
        d = entry.to_dict()
        assert d["instance_id"] == "django__1234"
        assert d["model_name_or_path"] == "gpt-4"
        assert d["model_patch"] == "diff content"

    def test_to_dict_none_patch(self) -> None:
        entry = PredEntry(
            instance_id="django__1234",
            model_name_or_path="gpt-4",
            model_patch=None,
        )
        d = entry.to_dict()
        assert d["model_patch"] == ""


class TestShouldRunInstance:
    def test_no_trajectory(self, tmp_path: Path) -> None:
        assert _should_run_instance(tmp_path, "inst_1", redo_existing=False) is True

    def test_existing_incomplete(self, tmp_path: Path) -> None:
        traj = tmp_path / "trajectory_inst_1.json"
        traj.write_text(json.dumps({"messages": []}))
        assert _should_run_instance(tmp_path, "inst_1", redo_existing=False) is True

    def test_existing_complete(self, tmp_path: Path) -> None:
        traj = tmp_path / "trajectory_inst_1.json"
        traj.write_text(json.dumps({"final_state": "SUBMITTED", "messages": []}))
        assert _should_run_instance(tmp_path, "inst_1", redo_existing=False) is False

    def test_redo_existing_true(self, tmp_path: Path) -> None:
        traj = tmp_path / "trajectory_inst_1.json"
        traj.write_text(json.dumps({"final_state": "SUBMITTED", "messages": []}))
        assert _should_run_instance(tmp_path, "inst_1", redo_existing=True) is True


class TestBatchResult:
    def test_merge(self) -> None:
        a = BatchResult(total=3, completed=2, failed=1, preds=[PredEntry("a", "m")])
        b = BatchResult(total=5, completed=4, failed=1, preds=[PredEntry("b", "m")])
        a.merge(b)
        assert a.total == 8
        assert a.completed == 6
        assert a.failed == 2
        assert len(a.preds) == 2
