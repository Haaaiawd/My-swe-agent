"""Live CLI progress display for mini-swe-agent run command.

Renders a real-time status panel using Rich's Live system.
Streaming model tokens are captured via token_callback and shown inside
the panel — NOT printed to stdout — so there is no terminal corruption.

Layout (updates in-place):
┌─────────────────────────────────────────────────────────────────────────────┐
│  mini-swe-agent  ● running   model: deepseek-v4-flash                       │
│  Step   3 / 80  [███░░░░░░░░░░░░░░░░░░]  Cost $0.0012  Elapsed 0:42        │
│  ❯  echo hello world                                                        │
│  ··· thinking: def foo(): return 1...                                       │
└─────────────────────────────────────────────────────────────────────────────┘

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

# Max chars of streaming token buffer shown in the panel
_TOKEN_PREVIEW_LEN = 120


def _fmt_elapsed(seconds: float) -> str:
    """Format elapsed seconds as M:SS or H:MM:SS."""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def _make_panel(
    step: int,
    step_limit: int,
    command: str,
    cost: float,
    elapsed: float,
    status: str,
    model: str,
    token_preview: str,
) -> Panel:
    """Build a Rich Panel with the current run status."""
    dot_color = _GREEN if status == "running" else _YELLOW

    # Row 1: brand + status + model
    row1 = Text()
    row1.append(f"  {_BRAND}  ", style="bold white")
    row1.append("● ", style=dot_color)
    row1.append(status, style=dot_color)
    row1.append("   model: ", style=_DIM)
    row1.append(model.split("/")[-1], style=_DIM)

    # Row 2: progress bar + cost + elapsed
    bar_width = 20
    filled = int(bar_width * step / max(step_limit, 1))
    bar = "█" * filled + "░" * (bar_width - filled)
    elapsed_str = _fmt_elapsed(elapsed)
    row2 = Text()
    row2.append("  Step ", style=_DIM)
    row2.append(f"{step:>3}", style="bold white")
    row2.append(f" / {step_limit}  ", style=_DIM)
    row2.append(f"[{bar}]  ", style=_CYAN)
    row2.append("Cost ", style=_DIM)
    row2.append(f"${cost:.4f}", style="bold " + _YELLOW)
    row2.append("  Elapsed ", style=_DIM)
    row2.append(elapsed_str, style="white")

    # Row 3: last executed command
    cmd_preview = command[:120] if command else "(waiting for model...)"
    row3 = Text()
    row3.append("  ❯  ", style="bold " + _GREEN)
    row3.append(cmd_preview, style="italic white")

    # Row 4: streaming token preview (only shown while model is thinking)
    lines: list[Any] = [row1, "\n", row2, "\n", row3]
    if token_preview:
        # Collapse newlines to keep the panel single-height
        preview = token_preview.replace("\n", " ").replace("\r", "")[-_TOKEN_PREVIEW_LEN:]
        row4 = Text()
        row4.append("  ··· ", style=_DIM)
        row4.append(preview, style="dim italic white")
        lines += ["\n", row4]

    content = Text.assemble(*lines)
    return Panel(
        content,
        border_style=_GREEN if status == "running" else _YELLOW,
        padding=(0, 1),
    )


class LiveDisplay:
    """Manages the Rich Live panel for a single agent run.

    Provides two callbacks for the state machine:
    - ``on_step(step, command, cost)``  — called after each completed step
    - ``on_token(token)``               — called per streamed model token
    """

    def __init__(self, step_limit: int, model: str) -> None:
        self._step_limit = step_limit
        self._model = model
        self._step = 0
        self._command = ""
        self._cost = 0.0
        self._status = "running"
        self._start = time.monotonic()
        self._token_buf = ""          # accumulates tokens between steps
        # Single console on stderr; Rich Live owns the terminal area
        self._console = Console(stderr=True)
        self._live: Live | None = None

    def start(self) -> None:
        """Start the live display."""
        self._live = Live(
            self._render(),
            console=self._console,
            refresh_per_second=8,
            transient=False,
        )
        self._live.start()

    def stop(self, final_state: str) -> None:
        """Stop the live display and print a final summary line."""
        self._status = final_state
        self._token_buf = ""
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
        self._token_buf = ""   # clear token buffer once step is done
        if self._live:
            self._live.update(self._render())

    def on_token(self, token: str) -> None:
        """Callback per streamed model token — shown in the panel preview row."""
        self._token_buf += token
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
            token_preview=self._token_buf,
        )


@contextmanager
def live_run_display(
    step_limit: int,
    model: str,
) -> Any:
    """Context manager that yields a LiveDisplay; stops it on exit.

    Usage::

        with live_run_display(step_limit=80, model="gpt-4o") as display:
            agent.run(task, step_callback=display.on_step,
                      token_callback=display.on_token)
    """
    display = LiveDisplay(step_limit=step_limit, model=model)
    display.start()
    try:
        yield display
    finally:
        pass  # caller calls display.stop(final_state) explicitly
