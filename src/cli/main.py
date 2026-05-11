"""CLI main entry-point using click.

Registers run, batch, and check subcommands (placeholders for S3).
Risk warning included in --help output per ADR-001.

Core logic: click group with three subcommands and --version.
Dependencies: click.
Test coverage: INT-S1 smoke test (mini-swe-agent --help).
"""

from __future__ import annotations

import click


@click.group(
    help=(
        "mini SWE Agent — automated programming task evaluation.\n\n"
        "⚠️  This tool executes shell commands automatically. Use with caution."
    )
)
@click.version_option(version="0.1.0", prog_name="mini-swe-agent")
def cli() -> None:
    """mini SWE Agent CLI."""
    pass


@cli.command(name="run", help="Run a single task.")
def run_cmd() -> None:
    """Placeholder for the run subcommand (T3.1.2)."""
    click.echo("run: not yet implemented (T3.1.2)")


@cli.command(name="batch", help="Batch process multiple tasks.")
def batch_cmd() -> None:
    """Placeholder for the batch subcommand (T3.1.3)."""
    click.echo("batch: not yet implemented (T3.1.3)")


@cli.command(name="check", help="Inspect a trajectory file (TUI).")
def check_cmd() -> None:
    """Placeholder for the check subcommand (T3.1.4)."""
    click.echo("check: not yet implemented (T3.1.4)")


def main() -> None:
    """Entry-point for the mini-swe-agent console script."""
    cli()


if __name__ == "__main__":
    main()
