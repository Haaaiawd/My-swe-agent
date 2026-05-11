"""Executor: shell command execution via subprocess.

Uses ``shlex.split(posix=not is_windows)`` with ``shell=False`` for safety.
Captures returncode, stdout, stderr, and preserves the original stdout
in ``stdout_original`` for submission-marker detection (ADR-006).

Timeout (subprocess.TimeoutExpired) terminates the process and records
``error_type="TIMEOUT"``; no retries are performed (ADR-003).

Dependencies: os, shlex, subprocess; core.models.ExecutionResult.
Test coverage: tests/unit/test_executor.py.
"""

from __future__ import annotations

import os
import shlex
import subprocess

from core.models import ExecutionResult


def execute_command(command: str, timeout: float = 10.0) -> ExecutionResult:
    """Execute *command* via subprocess with *timeout* seconds.

    Args:
        command: The shell command string to execute.
        timeout: Maximum seconds to wait (default 10).

    Returns:
        ExecutionResult containing returncode, stdout, stderr, and
        stdout_original (untruncated raw stdout).
    """
    try:
        posix_mode = os.name != "nt"
        args = shlex.split(command, posix=posix_mode)
        result = subprocess.run(
            args,
            shell=False,
            timeout=timeout,
            capture_output=True,
            text=True,
            check=False,
        )
        return ExecutionResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            stdout_original=result.stdout,
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(
            returncode=-1,
            stdout="",
            stderr=f"Command timed out after {timeout}s",
            stdout_original="",
            exception_metadata={"error_type": "TIMEOUT"},
        )
    except (OSError, ValueError, TypeError) as e:
        return ExecutionResult(
            returncode=-1,
            stdout="",
            stderr=str(e),
            stdout_original="",
            exception_metadata={"error_type": type(e).__name__},
        )
