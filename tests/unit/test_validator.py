"""Unit tests for CommandValidator.

Covers: blacklist hit, destructive+flag combo, normal command pass, empty command.
"""

from __future__ import annotations

import pytest

from core.models import CommandValidationError
from core.validator import validate_command


class TestValidateCommand:
    def test_rm_rf_root_blocked(self):
        with pytest.raises(CommandValidationError):
            validate_command("rm -rf /")

    def test_echo_hello_passes(self):
        # Should not raise
        validate_command("echo hello")

    def test_rm_f_passes_dangerous_flag(self):
        with pytest.raises(CommandValidationError) as exc:
            validate_command("rm -f /etc/passwd")
        assert "Dangerous flag" in exc.value.reason

    def test_empty_command(self):
        with pytest.raises(CommandValidationError):
            validate_command("")

    def test_whitespace_only_command(self):
        with pytest.raises(CommandValidationError):
            validate_command("   ")

    def test_mkfs_blocked(self):
        with pytest.raises(CommandValidationError):
            validate_command("mkfs /dev/sda1")

    def test_dd_if_dev_zero_blocked(self):
        with pytest.raises(CommandValidationError):
            validate_command("dd if=/dev/zero of=/dev/sda")
