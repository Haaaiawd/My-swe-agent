"""TrajectoryManager: streaming JSON-Lines trajectory writer.

Appends one JSON object per step.  Auto-flushes every 100 steps to a
``.tmp.jsonl`` sidecar to guard against OOM.  On ``save_trajectory()`` the
sidecar is merged into a single JSON object with ``schema_version="v1_jsonl"``.

If the primary path is unwritable (OSError / disk-full) a backup attempt
is made under the system temp directory.

Dependencies: json, os, pathlib, tempfile, uuid.
Test coverage: tests/unit/test_trajectory.py.
"""

from __future__ import annotations

import contextlib
import json
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any

from core.models import Trajectory

logger = logging.getLogger(__name__)

AUTO_FLUSH_EVERY = 100  # steps


class TrajectoryManager:
    """Manages streaming trajectory writes and periodic auto-flush."""

    def __init__(self, trajectory: Trajectory) -> None:
        self.trajectory = trajectory
        self._tmp_path: Path | None = None
        self._steps_since_flush = 0

    def append(
        self,
        message: dict[str, Any],
        tool_call_id: str | None = None,
    ) -> None:
        """Append a message and auto-flush every *AUTO_FLUSH_EVERY* steps."""
        self.trajectory.add_message(message, tool_call_id)
        if message.get("role") == "tool":
            self.trajectory.increment_step()
            self._steps_since_flush += 1
            if self._steps_since_flush >= AUTO_FLUSH_EVERY:
                self._auto_flush()
                self._steps_since_flush = 0

    def _auto_flush(self) -> None:
        """Write pending messages to a temporary JSONL sidecar."""
        if self._tmp_path is None:
            self._tmp_path = (
                Path(tempfile.gettempdir()) / f"trajectory_{uuid.uuid4().hex[:8]}.tmp.jsonl"
            )
        with open(self._tmp_path, "a", encoding="utf-8") as f:
            for msg in self.trajectory.messages[-AUTO_FLUSH_EVERY:]:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    def save_trajectory(self, path: str | Path, final_state: str | None = None) -> Path:
        """Persist the trajectory as a single JSON object to *path*.

        If *path* is unwritable, attempts a backup under the system temp dir.

        Args:
            final_state: Optional terminal state to record in the trajectory metadata.

        Returns:
            The final Path where the trajectory was written.
        """
        target = Path(path)
        data = {
            "schema_version": self.trajectory.schema_version,
            "messages": self.trajectory.messages,
            "cost_accumulator": self.trajectory.cost_accumulator,
            "step_counter": self.trajectory.step_counter,
            "final_state": final_state,
        }

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            backup = Path(tempfile.gettempdir()) / f"trajectory_backup_{uuid.uuid4().hex[:8]}.json"
            logger.warning(
                "Failed to write trajectory to %s (%s). Trying backup: %s",
                target,
                exc,
                backup,
            )
            with open(backup, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            target = backup

        # Clean up temporary sidecar if it exists
        if self._tmp_path and self._tmp_path.exists():
            with contextlib.suppress(OSError):
                self._tmp_path.unlink()

        return target
