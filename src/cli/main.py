"""CLI main entry-point using click.

Registers run, batch, and check subcommands.
Risk warning included in --help output per ADR-001.

Core logic:
  - click group with three subcommands and --version.
  - run: loads config via ConfigManager, runs Agent, maps returncode to CLI exit code.
  - batch / check: placeholders (T3.1.3 / T3.1.4).

Dependencies: click, pathlib, json, datetime.
Test coverage: tests/integration/test_cli_run.py, tests/unit/test_exit_codes.py.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from cli.exit_codes import EXIT_CODES, map_agent_result_to_exit_code
from config import ConfigError, ConfigManager
from core.agent import Agent

# ── Risk banner ───────────────────────────────────────────────

_RISK_BANNER = """\
⚠️  Warning: This tool executes shell commands automatically.
    Review the task description and configuration before running.
    Use --yolo with caution.
"""


def _print_risk_banner() -> None:
    """Print the risk warning banner to stderr."""
    click.echo(_RISK_BANNER, err=True)


def _confirm_continue() -> bool:
    """Prompt the user to confirm continuation; return True if confirmed."""
    try:
        return click.confirm("Continue?", default=False)
    except click.Abort:
        return False


# ── Diagnostic helper ─────────────────────────────────────────

_DIAGNOSTIC_FILENAME_TEMPLATE = "config_error_{timestamp}.txt"


def _write_diagnostic_file(output_dir: Path, exc: ConfigError) -> Path:
    """Write a minimal diagnostic JSON when ConfigError occurs.

    Returns the path to the written file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = _DIAGNOSTIC_FILENAME_TEMPLATE.format(timestamp=timestamp)
    diag_path = output_dir / filename
    diagnostic = {
        "error_type": "ConfigError",
        "message": exc.message,
        "file_path": exc.file_path,
        "line": exc.line,
        "variable": exc.variable,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    diag_path.write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
    return diag_path


# ── Summary helper ────────────────────────────────────────────


def _print_summary(result: Any) -> None:
    """Print a human-readable summary of the agent run result."""
    click.echo(f"Final state : {result.final_state}")
    click.echo(f"Return code : {result.returncode}")
    click.echo(f"Trajectory  : {result.trajectory_path}")
    if result.overall_output:
        click.echo(f"Output len  : {len(result.overall_output)} chars")


# ── CLI group ─────────────────────────────────────────────────


@click.group(
    help=(
        "mini SWE Agent — automated programming task evaluation.\n\n"
        "⚠️  This tool executes shell commands automatically. Use with caution."
    )
)
@click.version_option(version="0.2.0", prog_name="mini-swe-agent")
def cli() -> None:
    """mini SWE Agent CLI."""
    pass


# ── run subcommand ────────────────────────────────────────────


@cli.command(name="run", help="Run a single task.")
@click.option(
    "--config",
    "-c",
    "config_paths",
    required=True,
    multiple=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path(s) to YAML configuration file(s). Can be specified multiple times.",
)
@click.option("--model", "-m", type=str, default=None, help="Override model name.")
@click.option(
    "--yolo",
    is_flag=True,
    default=False,
    help="Skip confirmation prompt and run immediately.",
)
@click.option(
    "--step-limit",
    type=int,
    default=None,
    help="Override the agent step limit.",
)
@click.option(
    "--cost-limit",
    type=float,
    default=None,
    help="Override the agent cost limit (USD).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("./outputs"),
    help="Directory for trajectory and diagnostic files.",
)
@click.option("--verbose", "-v", is_flag=True, default=False, help="Print summary after run.")
@click.option("--task", type=str, default=None, help="Override task description.")
@click.option(
    "--exit-immediately",
    is_flag=True,
    default=None,
    help="Override agent exit_immediately flag.",
)
def run_cmd(
    config_paths: tuple[Path, ...],
    model: str | None,
    yolo: bool,
    step_limit: int | None,
    cost_limit: float | None,
    output: Path,
    verbose: bool,
    task: str | None,
    exit_immediately: bool | None,
) -> None:
    """Run a single task through the agent loop.

    Loads configuration, optionally overrides model/step/cost limits,
    executes the agent, and maps the final returncode to a CLI exit code.
    """
    _print_risk_banner()
    if not yolo and not _confirm_continue():
        sys.exit(EXIT_CODES["USER_DECLINED"])

    # Load configuration
    mgr = ConfigManager()
    try:
        cfg = mgr.load_config(config_paths=[str(c) for c in config_paths], env_prefix="MINI_SWE")
    except ConfigError as exc:
        click.echo(f"Configuration error: {exc.message}", err=True)
        diag_path = _write_diagnostic_file(output, exc)
        click.echo(f"Diagnostic written to: {diag_path}", err=True)
        sys.exit(EXIT_CODES["AGENT_FATAL_CONFIG"])

    # Apply CLI overrides
    if model is not None:
        if isinstance(cfg.get("model"), dict):
            cfg["model"]["name"] = model
        else:
            cfg["model"] = {"name": model}

    if step_limit is not None:
        if "agent" not in cfg or not isinstance(cfg["agent"], dict):
            cfg["agent"] = {}
        cfg["agent"]["step_limit"] = step_limit

    if cost_limit is not None:
        if "agent" not in cfg or not isinstance(cfg["agent"], dict):
            cfg["agent"] = {}
        cfg["agent"]["cost_limit"] = cost_limit

    if task is not None:
        cfg["task_description"] = task

    if exit_immediately is not None:
        if "agent" not in cfg or not isinstance(cfg["agent"], dict):
            cfg["agent"] = {}
        cfg["agent"]["exit_immediately"] = exit_immediately

    # Ensure output directory exists and set trajectory path
    output.mkdir(parents=True, exist_ok=True)
    if "output" not in cfg or not isinstance(cfg["output"], dict):
        cfg["output"] = {}
    cfg["output"]["trajectory_path"] = str(output / "trajectory.json")

    # Run agent
    agent = Agent(cfg)
    task_description = cfg.get("task_description", "")

    def _confirm_step(command: str) -> bool:
        return click.confirm(f"Execute: {command}?", default=False)

    if yolo:
        result = agent.run(task_description)
    else:
        result = agent.run(task_description, confirm_callback=_confirm_step)

    if verbose:
        _print_summary(result)

    cli_exit = map_agent_result_to_exit_code(result.returncode)
    sys.exit(cli_exit)


# ── batch subcommand ──────────────────────────────────────────


@cli.command(name="batch", help="Batch process multiple tasks.")
@click.argument("dataset", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--config",
    "-c",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to the global YAML configuration file.",
)
@click.option(
    "--workers",
    "-w",
    type=int,
    default=None,
    help="Number of parallel workers (default: CPU count, cap=64).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path("./preds.json"),
    help="Path for preds.json output.",
)
@click.option(
    "--output-dir",
    "-d",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("./outputs"),
    help="Directory for trajectory files.",
)
@click.option(
    "--filter",
    type=str,
    default=None,
    help="Regex filter for instance_id.",
)
@click.option(
    "--slice",
    type=str,
    default=None,
    help="Slice range 'start:stop' for the dataset.",
)
@click.option(
    "--shuffle-seed",
    type=int,
    default=None,
    help="Deterministic shuffle seed.",
)
@click.option(
    "--redo-existing",
    is_flag=True,
    default=False,
    help="Re-run instances that already have trajectories.",
)
@click.option("--yolo", is_flag=True, default=False, help="Skip confirmation prompt.")
def batch_cmd(
    dataset: Path,
    config: Path,
    workers: int | None,
    output: Path,
    output_dir: Path,
    filter: str | None,
    slice: str | None,
    shuffle_seed: int | None,
    redo_existing: bool,
    yolo: bool,
) -> None:
    """Batch process a dataset directory containing instance.jsonl."""
    from cli.batch import BatchConfig, batch_run

    _print_risk_banner()
    if not yolo and not _confirm_continue():
        sys.exit(EXIT_CODES["USER_DECLINED"])

    slice_range: tuple[int, int] | None = None
    if slice is not None:
        parts = slice.split(":")
        if len(parts) != 2:
            raise click.BadParameter("slice must be 'start:stop'")
        slice_range = (int(parts[0]), int(parts[1]))

    batch_config = BatchConfig(
        dataset_path=dataset,
        global_config_path=config,
        workers=workers if workers is not None else (os.cpu_count() or 1),
        filter_regex=filter,
        slice_range=slice_range,
        shuffle_seed=shuffle_seed,
        redo_existing=redo_existing,
        output_path=output,
        output_dir=output_dir,
    )

    exit_code = batch_run(batch_config)
    sys.exit(exit_code)


# ── check subcommand ────────────────────────────────────────────


@cli.command(name="check", help="Inspect a trajectory file (TUI).")
@click.argument(
    "trajectory",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
def check_cmd(trajectory: Path) -> None:
    """Launch Textual TUI to inspect a trajectory JSON file."""
    from cli.checker import check_trajectory

    check_trajectory(trajectory)


# ── Entry-point ─────────────────────────────────────────────


def main() -> None:
    """Entry-point for the mini-swe-agent console script."""
    cli()


if __name__ == "__main__":
    main()
