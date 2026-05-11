"""Batch processing subcommand for mini-swe-agent.

Supports multiprocessing concurrent execution, dataset filtering/slicing/shuffle,
trajectory integrity checks, and preds.json generation per SWE-bench schema.

Reference: cli-system.detail.md §3.2, §2.1, §2.2.
Test coverage: tests/unit/test_batch.py, tests/integration/test_batch_smoke.py.
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cli.exit_codes import EXIT_CODES
from config import ConfigError, ConfigManager
from core.agent import Agent
from core.models import AgentResult

logger = logging.getLogger(__name__)

MAX_WORKERS_CAP = 64
BATCH_SCHEMA_VERSION = "v1"


# ── Data structures ───────────────────────────────────────────


@dataclass
class BatchConfig:
    """Batch processing configuration."""

    dataset_path: Path
    global_config_path: Path
    workers: int = field(default_factory=lambda: os.cpu_count() or 1)
    filter_regex: str | None = None
    slice_range: tuple[int, int] | None = None
    shuffle_seed: int | None = None
    redo_existing: bool = False
    output_path: Path = field(default_factory=lambda: Path("./preds.json"))
    output_dir: Path = field(default_factory=lambda: Path("./outputs"))

    def __post_init__(self) -> None:
        """Validate and normalize configuration."""
        if self.workers < 1:
            raise ValueError(f"workers must be >= 1, got {self.workers}")
        if self.workers > MAX_WORKERS_CAP:
            warnings.warn(
                f"workers capped from {self.workers} to {MAX_WORKERS_CAP}",
                stacklevel=2,
            )
            self.workers = MAX_WORKERS_CAP

        self.dataset_path = self.dataset_path.resolve()
        self.output_path = self.output_path.resolve()
        self.output_dir = self.output_dir.resolve()

        if self.slice_range is not None:
            start, stop = self.slice_range
            if start < 0 or stop < 0:
                raise ValueError("slice_range must be non-negative")
            if start >= stop:
                raise ValueError("slice_range start must be < stop")


@dataclass
class PredEntry:
    """Single entry for preds.json (SWE-bench schema)."""

    instance_id: str
    model_name_or_path: str
    model_patch: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to preds.json entry."""
        return {
            "instance_id": self.instance_id,
            "model_name_or_path": self.model_name_or_path,
            "model_patch": self.model_patch or "",
        }


@dataclass
class BatchResult:
    """Aggregated batch execution results."""

    total: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    preds: list[PredEntry] = field(default_factory=list)
    output_path: Path = field(default_factory=lambda: Path("./preds.json"))

    def merge(self, other: BatchResult) -> None:
        """Merge another BatchResult (for multi-process aggregation)."""
        self.total += other.total
        self.completed += other.completed
        self.failed += other.failed
        self.skipped += other.skipped
        self.preds.extend(other.preds)


# ── Helpers ───────────────────────────────────────────────────


def _load_instances(dataset_path: Path) -> list[dict[str, Any]]:
    """Load instance.jsonl from dataset directory."""
    instance_file = dataset_path / "instance.jsonl"
    if not instance_file.exists():
        raise FileNotFoundError(f"Dataset file not found: {instance_file}")

    instances = []
    with open(instance_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                instances.append(json.loads(line))
    return instances


def _should_run_instance(output_dir: Path, instance_id: str, redo_existing: bool) -> bool:
    """Check if an instance should be run based on trajectory integrity.

    A complete trajectory must contain a 'final_state' field.
    """
    if redo_existing:
        return True
    traj_path = output_dir / f"trajectory_{instance_id}.jsonl"
    if not traj_path.exists():
        return True
    try:
        with open(traj_path, encoding="utf-8") as f:
            data = json.loads(f.read())
        return "final_state" not in data
    except (OSError, json.JSONDecodeError):
        return True


def _compute_task_timeout(global_config_path: Path) -> float:
    """Compute per-task timeout from global config (step_limit * step_timeout + 30s buffer)."""
    try:
        cfg = ConfigManager().load_config(
            config_paths=[str(global_config_path)], env_prefix="MINI_SWE"
        )
    except ConfigError:
        cfg = {}

    agent_cfg = cfg.get("agent", {})
    step_limit = agent_cfg.get("step_limit", 100)
    step_timeout = agent_cfg.get("step_timeout", 120)
    computed = step_limit * step_timeout + 30.0

    explicit = cfg.get("batch", {}).get("task_timeout")
    if explicit is not None:
        return float(explicit)
    return computed


# ── Worker function (must be top-level for ProcessPoolExecutor spawn) ──


def _run_single_instance(
    instance: dict[str, Any], config_path: str, output_dir: str
) -> AgentResult:
    """Run a single instance in a worker process.

    Returns AgentResult with trajectory_path, final_state, overall_output, returncode.
    """
    instance_id = instance.get("instance_id", "unknown")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    traj_path = out_dir / f"trajectory_{instance_id}.jsonl"

    mgr = ConfigManager()
    try:
        cfg = mgr.load_config(config_paths=[config_path], env_prefix="MINI_SWE")
    except ConfigError as exc:
        logger.error("ConfigError for instance %s: %s", instance_id, exc.message)
        return AgentResult(
            trajectory_path=traj_path,
            final_state="FATAL_CONFIG",
            overall_output=None,
            returncode=5,
            model_name="unknown",
            error=exc.message,
        )

    # Set trajectory path
    if "output" not in cfg or not isinstance(cfg["output"], dict):
        cfg["output"] = {}
    cfg["output"]["trajectory_path"] = str(traj_path)

    # Derive task description from instance metadata
    task = instance.get("task_description", instance.get("problem_statement", ""))

    agent = Agent(cfg)
    try:
        return agent.run(task)
    except Exception as exc:
        logger.exception("Unexpected error running instance %s: %s", instance_id, exc)
        return AgentResult(
            trajectory_path=traj_path,
            final_state="UNKNOWN_ERROR",
            overall_output=None,
            returncode=6,
            model_name=cfg.get("model", {}).get("name", "unknown"),
            error=str(exc),
        )


# ── Core batch logic ──────────────────────────────────────────


def batch_run(batch_config: BatchConfig) -> int:
    """Execute batch processing and return CLI exit code.

    Side effects:
      - Writes trajectory files to output_dir
      - Writes preds.json to output_path
    """
    instances = _load_instances(batch_config.dataset_path)

    # Filter
    if batch_config.filter_regex:
        pattern = re.compile(batch_config.filter_regex)
        instances = [i for i in instances if pattern.search(i.get("instance_id", ""))]

    # Slice
    if batch_config.slice_range:
        start, stop = batch_config.slice_range
        instances = instances[start:stop]

    # Deterministic shuffle
    if batch_config.shuffle_seed is not None:
        rng = random.Random(batch_config.shuffle_seed)
        rng.shuffle(instances)

    # Check existing trajectories
    tasks_to_run: list[dict[str, Any]] = []
    for inst in instances:
        if _should_run_instance(
            batch_config.output_dir,
            inst.get("instance_id", ""),
            batch_config.redo_existing,
        ):
            tasks_to_run.append(inst)

    total = len(instances)
    skipped = total - len(tasks_to_run)

    # Compute timeout
    task_timeout = _compute_task_timeout(batch_config.global_config_path)

    # Concurrent execution
    results: list[AgentResult] = []
    failed_count = 0

    with ProcessPoolExecutor(max_workers=batch_config.workers) as executor:
        futures = {
            executor.submit(
                _run_single_instance,
                instance=inst,
                config_path=str(batch_config.global_config_path),
                output_dir=str(batch_config.output_dir),
            ): inst
            for inst in tasks_to_run
        }

        for future in as_completed(futures):
            inst = futures[future]
            try:
                result = future.result(timeout=task_timeout)
                results.append(result)
            except Exception as exc:
                logger.error("Instance %s failed: %s", inst.get("instance_id"), exc)
                failed_count += 1

    # Aggregate preds.json: only SUBMITTED (returncode==0) with non-empty overall_output
    preds = []
    for result in results:
        if result.returncode == 0 and result.overall_output:
            preds.append(
                PredEntry(
                    instance_id=_extract_instance_id(result.trajectory_path),
                    model_name_or_path=result.model_name,
                    model_patch=result.overall_output,
                )
            )

    batch_result = BatchResult(
        total=total,
        completed=len(results) - failed_count,
        failed=failed_count,
        skipped=skipped,
        preds=preds,
        output_path=batch_config.output_path,
    )

    _write_preds_json(batch_result)
    _print_batch_summary(batch_result)

    if batch_result.failed == 0:
        return EXIT_CODES["SUCCESS"]
    elif batch_result.completed > 0:
        return EXIT_CODES["BATCH_PARTIAL_FAILURE"]
    else:
        return EXIT_CODES["AGENT_UNKNOWN_ERROR"]


# ── Output helpers ────────────────────────────────────────────


def _extract_instance_id(trajectory_path: Path) -> str:
    """Extract instance_id from trajectory file path.

    Expects path like .../trajectory_<instance_id>.jsonl
    """
    stem = trajectory_path.stem
    if stem.startswith("trajectory_"):
        return stem[len("trajectory_") :]
    return stem


def _write_preds_json(batch_result: BatchResult) -> None:
    """Write preds.json in SWE-bench schema format."""
    batch_result.output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": BATCH_SCHEMA_VERSION,
        "predictions": [p.to_dict() for p in batch_result.preds],
    }
    with open(batch_result.output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _print_batch_summary(batch_result: BatchResult) -> None:
    """Print human-readable batch summary."""
    import click

    click.echo("\n=== Batch Summary ===")
    click.echo(f"Total   : {batch_result.total}")
    click.echo(f"Completed: {batch_result.completed}")
    click.echo(f"Failed  : {batch_result.failed}")
    click.echo(f"Skipped : {batch_result.skipped}")
    click.echo(f"Preds   : {len(batch_result.preds)}")
    click.echo(f"Output  : {batch_result.output_path}")
    click.echo("=" * 22)
