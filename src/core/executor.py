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

import logging
import subprocess

from core.models import ExecutionResult

logger = logging.getLogger(__name__)


def execute_command(command: str, timeout: float = 10.0) -> ExecutionResult:
    """Execute *command* via subprocess with *timeout* seconds.

    Uses ``shell=True`` so the command string is interpreted by the system
    shell, preserving pipes, redirections, and built-in commands.

    Args:
        command: The shell command string to execute.
        timeout: Maximum seconds to wait (default 10).

    Returns:
        ExecutionResult containing returncode, stdout, stderr, and
        stdout_original (untruncated raw stdout).
    """
    logger.info("Executing command: %s", command)
    try:
        result = subprocess.run(
            command,
            shell=True,
            timeout=timeout,
            capture_output=True,
            text=True,
            check=False,
        )
        logger.info(
            "Command finished with returncode %d (stdout %d chars, stderr %d chars)",
            result.returncode,
            len(result.stdout),
            len(result.stderr),
        )
        return ExecutionResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            stdout_original=result.stdout,
        )
    except subprocess.TimeoutExpired:
        logger.warning("Command timed out after %s seconds: %s", timeout, command)
        return ExecutionResult(
            returncode=-1,
            stdout="",
            stderr=f"Command timed out after {timeout}s",
            stdout_original="",
            exception_metadata={"error_type": "TIMEOUT"},
        )
    except (OSError, ValueError, TypeError) as e:
        logger.error("Command execution failed: %s — %s", command, e)
        return ExecutionResult(
            returncode=-1,
            stdout="",
            stderr=str(e),
            stdout_original="",
            exception_metadata={"error_type": type(e).__name__},
        )
