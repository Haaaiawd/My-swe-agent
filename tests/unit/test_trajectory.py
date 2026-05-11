"""Unit tests for TrajectoryManager.

Covers: append with tool_call_id, step counter, 100-step auto-flush,
save_trajectory schema, OSError backup path.
"""

from __future__ import annotations

import json

from core.models import Trajectory
from core.trajectory import TrajectoryManager


class TestTrajectoryManager:
    def test_append_message(self):
        traj = Trajectory()
        mgr = TrajectoryManager(traj)
        mgr.append({"role": "assistant", "content": "hello"}, tool_call_id="tc_1")
        assert len(traj.messages) == 1
        assert traj.messages[0]["tool_call_id"] == "tc_1"

    def test_step_counter(self):
        traj = Trajectory()
        mgr = TrajectoryManager(traj)
        for _ in range(3):
            mgr.append({"role": "tool", "content": "ok"})
        assert traj.step_counter == 3

    def test_save_trajectory_schema(self, tmp_path):
        traj = Trajectory()
        mgr = TrajectoryManager(traj)
        mgr.append({"role": "tool", "content": "ok"}, tool_call_id="tc_1")
        path = tmp_path / "traj.json"
        saved = mgr.save_trajectory(str(path))
        assert saved == path
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["schema_version"] == "v1_jsonl"
        assert "messages" in data
        assert data["messages"][0]["tool_call_id"] == "tc_1"

    def test_100_step_auto_flush(self, tmp_path, monkeypatch):
        traj = Trajectory()
        mgr = TrajectoryManager(traj)
        tmp_file = tmp_path / "flush.tmp.jsonl"
        monkeypatch.setattr(mgr, "_tmp_path", tmp_file)
        # Append 100 tool messages
        for i in range(100):
            mgr.append({"role": "tool", "content": f"msg{i}"})
        # Auto-flush should have triggered
        assert tmp_file.exists()
        lines = tmp_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 100

    def test_os_error_backup(self, tmp_path):
        traj = Trajectory()
        mgr = TrajectoryManager(traj)
        mgr.append({"role": "tool", "content": "ok"})
        # Try to write to a read-only directory (simulate OSError)
        bad_path = tmp_path / "nonexistent" / "deep" / "dir" / "traj.json"
        # Make the parent unwritable by using a file as parent
        bad_path.parent.parent.mkdir(parents=True)
        bad_path.parent.parent.joinpath("dir").write_text("i am a file")
        saved = mgr.save_trajectory(str(bad_path))
        assert "trajectory_backup_" in str(saved)
        data = json.loads(saved.read_text(encoding="utf-8"))
        assert data["schema_version"] == "v1_jsonl"
