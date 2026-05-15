"""Executor: shell command execution via subprocess.

Uses ``shell=True`` so the command string is interpreted by the system shell,
preserving pipes, redirections, and built-ins.  Forces UTF-8 output decoding
with ``errors="replace"`` so Windows GBK/CP936 consoles never cause a
UnicodeDecodeError that silently drops all output (Windows-specific fix).

Timeout (subprocess.TimeoutExpired) terminates the process and records
``error_type="TIMEOUT"``; no retries are performed (ADR-003).

Dependencies: os, subprocess; core.models.ExecutionResult.
Test coverage: tests/unit/test_executor.py.
"""

from __future__ import annotations

import logging
import os
import subprocess

from core.models import ExecutionResult

logger = logging.getLogger(__name__)

# Force UTF-8 on Windows so GBK/CP936 console output never crashes the reader.
# PYTHONUTF8=1 is propagated to child processes; PYTHONIOENCODING covers the
# subprocess text-mode pipe decoder used by this process.
_CHILD_ENV: dict[str, str] | None = None
if os.name == "nt":
    _CHILD_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


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
            encoding="utf-8",
            errors="replace",
            env=_CHILD_ENV,
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
