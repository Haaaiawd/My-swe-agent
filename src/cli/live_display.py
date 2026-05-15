"""Live CLI progress display for mini-swe-agent run command.

Renders a real-time status panel using Rich's Live + Layout system.
Inspired by Claude Code / Codex style: persistent header bar showing
step progress, current command, cost, and elapsed time.

Layout (top of terminal, updates in-place):
┌─────────────────────────────────────────────────────────┐
│  mini-swe-agent  ●  running                             │
│  Step  3 / 80   Cost $0.0012   Elapsed 0:42             │
│  ❯  echo hello world                                    │
└─────────────────────────────────────────────────────────┘

Dependencies: rich (already in env via litellm transitive dep).
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

_BRAND = "mini-swe-agent"
_GREEN = "bright_green"
_DIM = "dim"
_YELLOW = "yellow"
_CYAN = "cyan"


def _make_panel(
    step: int,
    step_limit: int,
    command: str,
    cost: float,
    elapsed: float,
    status: str,
    model: str,
) -> Panel:
    """Build a Rich Panel with the current run status."""
    # Status dot
    dot_color = _GREEN if status == "running" else _YELLOW
    status_text = Text()
    status_text.append(f"  {_BRAND}  ", style="bold white")
    status_text.append("● ", style=dot_color)
    status_text.append(status, style=dot_color)
    status_text.append("   model: ", style=_DIM)
    status_text.append(model.split("/")[-1], style=_DIM)

    # Progress bar (ASCII, no external deps)
    bar_width = 20
    filled = int(bar_width * step / max(step_limit, 1))
    bar = "█" * filled + "░" * (bar_width - filled)

    # Stats row
    elapsed_str = _fmt_elapsed(elapsed)
    stats = Text()
    stats.append("  Step ", style=_DIM)
    stats.append(f"{step:>3}", style="bold white")
    stats.append(f" / {step_limit}  ", style=_DIM)
    stats.append(f"[{bar}]  ", style=_CYAN)
    stats.append("Cost ", style=_DIM)
    stats.append(f"${cost:.4f}", style="bold " + _YELLOW)
    stats.append("  Elapsed ", style=_DIM)
    stats.append(elapsed_str, style="white")

    # Command row
    cmd_preview = command[:120] if command else "(waiting for model...)"
    cmd_text = Text()
    cmd_text.append("  ❯  ", style="bold " + _GREEN)
    cmd_text.append(cmd_preview, style="italic white")

    content = Text.assemble(status_text, "\n", stats, "\n", cmd_text)
    return Panel(
        content,
        border_style=_GREEN if status == "running" else _YELLOW,
        padding=(0, 1),
    )


def _fmt_elapsed(seconds: float) -> str:
    """Format elapsed seconds as M:SS or H:MM:SS."""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


class LiveDisplay:
    """Manages the Rich Live panel for a single agent run."""

    def __init__(self, step_limit: int, model: str) -> None:
        self._step_limit = step_limit
        self._model = model
        self._step = 0
        self._command = ""
        self._cost = 0.0
        self._status = "running"
        self._start = time.monotonic()
        self._console = Console(stderr=True)  # stderr so it doesn't mix with streaming stdout
        self._live: Live | None = None

    def start(self) -> None:
        """Start the live display."""
        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=4,
            transient=False,
        )
        self._live.start()

    def stop(self, final_state: str) -> None:
        """Stop the live display and print a final summary line."""
        self._status = final_state
        if self._live:
            self._live.update(self._render())
            self._live.stop()

        elapsed = time.monotonic() - self._start
        icon = "✓" if final_state == "SUBMITTED" else "✗"
        color = "green" if final_state == "SUBMITTED" else "yellow"
        self._console.print(
            f"[{color}]{icon}  {final_state}[/{color}]  "
            f"[dim]{self._step} steps  ${self._cost:.4f}  {_fmt_elapsed(elapsed)}[/dim]"
        )

    def on_step(self, step: int, command: str, cost: float) -> None:
        """Callback for each completed step — called from state machine."""
        self._step = step
        self._command = command
        self._cost = cost
        if self._live:
            self._live.update(self._render())

    def _render(self) -> Panel:
        elapsed = time.monotonic() - self._start
        return _make_panel(
            step=self._step,
            step_limit=self._step_limit,
            command=self._command,
            cost=self._cost,
            elapsed=elapsed,
            status=self._status,
            model=self._model,
        )


@contextmanager
def live_run_display(
    step_limit: int,
    model: str,
) -> Any:
    """Context manager that yields a LiveDisplay; stops it on exit.

    Usage::

        with live_run_display(step_limit=80, model="gpt-4o") as display:
            agent.run(task, step_callback=display.on_step)
    """
    display = LiveDisplay(step_limit=step_limit, model=model)
    display.start()
    try:
        yield display
    finally:
        pass  # caller calls display.stop(final_state) explicitly
