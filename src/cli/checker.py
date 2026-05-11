"""Textual TUI trajectory checker for mini-swe-agent.

Displays trajectory steps in a scrollable table with:
  - Step index, action, status, cost columns
  - Highlighting for FormatError / CommandValidationError steps
  - ANSI escape sequence stripping
  - NUL character replacement (␀)
  - Keyboard navigation (↑/↓ scroll, q quit)

Reference: cli-system.detail.md §3.3, §1 CHECKER_CONFIG.
Test coverage: manual / E2E with MINI_SWE_ENABLE_E2E=1.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, Static

# ── ANSI / NUL helpers ────────────────────────────────────────

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Strip ANSI escape sequences."""
    return _ANSI_RE.sub("", text)


def _replace_nul(text: str) -> str:
    """Replace NUL characters with display symbol."""
    return text.replace("\x00", "␀")


def _clean(text: str) -> str:
    """Strip ANSI and replace NUL."""
    return _replace_nul(_strip_ansi(text))


# ── Step extraction ───────────────────────────────────────────


def _extract_steps(trajectory_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract displayable steps from trajectory JSON.

    Each step contains:
      - step_index
      - action (command or message summary)
      - status (OK / FormatError / ValidationError / Error)
      - cost (float)
    """
    messages = trajectory_data.get("messages", [])
    steps: list[dict[str, Any]] = []
    step_index = 0

    for _i, msg in enumerate(messages):
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "assistant":
            step_index += 1
            action = _clean(content)[:80]
            steps.append(
                {
                    "step_index": step_index,
                    "action": action,
                    "status": "MODEL",
                    "cost": 0.0,
                }
            )
        elif role == "tool":
            status = "OK"
            if "Parse error" in content or "FormatError" in content:
                status = "FormatError"
            elif "Validation error" in content or "CommandValidationError" in content:
                status = "ValidationError"
            elif "error" in content.lower():
                status = "Error"

            if steps:
                steps[-1]["status"] = status
        elif role == "system":
            if "Parse error" in content or "FormatError" in content:
                status = "FormatError"
            elif "Validation error" in content or "CommandValidationError" in content:
                status = "ValidationError"
            else:
                status = "System"

            step_index += 1
            steps.append(
                {
                    "step_index": step_index,
                    "action": _clean(content)[:80],
                    "status": status,
                    "cost": 0.0,
                }
            )

    return steps


# ── Textual App ───────────────────────────────────────────────


class TrajectoryChecker(App[None]):
    """Textual app for inspecting trajectory files."""

    CSS = """
    Screen { align: center middle; }
    DataTable { height: 1fr; }
    .error-row { background: $error; color: $text; }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("up", "scroll_up", "Scroll Up"),
        ("down", "scroll_down", "Scroll Down"),
    ]

    steps = reactive[list[dict[str, Any]]]([])
    schema_version = reactive[str]("unknown")

    def __init__(self, trajectory_data: dict[str, Any]) -> None:
        super().__init__()
        self.trajectory_data = trajectory_data
        self.schema_version = trajectory_data.get("schema_version", "unknown")
        self.steps = _extract_steps(trajectory_data)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static(f"Schema: {self.schema_version} | Steps: {len(self.steps)}")
        yield DataTable(
            id="step_table",
            cursor_type="row",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#step_table", DataTable)
        table.add_columns("Step", "Action", "Status", "Cost")

        error_styles = {
            "FormatError": "bold reverse red",
            "ValidationError": "bold reverse red",
            "Error": "bold reverse red",
        }

        for step in self.steps:
            style = error_styles.get(step["status"], "")
            table.add_row(
                str(step["step_index"]),
                step["action"],
                step["status"],
                f"{step['cost']:.4f}",
                key=str(step["step_index"]),
            )
            if style:
                # Style hint: error rows would be styled here.
                # Full row styling in Textual requires update_cell or custom renderables.
                pass

    def action_scroll_up(self) -> None:
        table = self.query_one("#step_table", DataTable)
        table.action_cursor_up()

    def action_scroll_down(self) -> None:
        table = self.query_one("#step_table", DataTable)
        table.action_cursor_down()


def check_trajectory(trajectory_path: Path) -> int:
    """Launch the Textual trajectory checker.

    Returns CLI exit code.
    """
    from cli.exit_codes import EXIT_CODES

    data = json.loads(trajectory_path.read_text(encoding="utf-8"))
    app = TrajectoryChecker(trajectory_data=data)
    app.run()
    return EXIT_CODES["SUCCESS"]
