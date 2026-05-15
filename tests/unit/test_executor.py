"""Unit tests for Executor.

Covers: normal execution, stdout_original preservation, timeout, OSError.
"""

from __future__ import annotations

import sys

from core.executor import execute_command


class TestExecuteCommand:
    def test_echo_hello(self):
        result = execute_command("echo hello", timeout=10)
        assert result.returncode == 0
        assert "hello" in result.stdout
        assert result.stdout_original == result.stdout

    def test_stderr_capture(self):
        # Write to stderr via python -c (cross-platform)
        result = execute_command(
            f'{sys.executable} -c "import sys; sys.stderr.write(\\"err\\")"',
            timeout=10,
        )
        assert "err" in result.stderr

    def test_timeout(self):
        # Use a long sleep that will definitely timeout
        result = execute_command("sleep 100", timeout=0.1)
        assert result.returncode == -1
        assert result.exception_metadata is not None
        assert result.exception_metadata.get("error_type") == "TIMEOUT"

    def test_stdout_original_preserved(self):
        result = execute_command("echo original", timeout=10)
        assert result.stdout_original == "original\n" or result.stdout_original == "original"

    def test_invalid_command_nonzero(self):
        # On Windows with shell=True, unknown commands return nonzero (e.g. 1)
        # instead of triggering OSError; on POSIX they return 127.
        # Either way the returncode must be nonzero, which the caller treats as failure.
        result = execute_command("this_should_not_exist_anywhere_12345", timeout=10)
        assert result.returncode != 0
