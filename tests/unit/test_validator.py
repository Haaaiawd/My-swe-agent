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

    # ── CH-R5-02: whitelist mode ─────────────────────────────────

    def test_whitelist_allows_explicit_command(self):
        # echo is in the whitelist
        validate_command("echo hello", whitelist=["echo", "cat"])

    def test_whitelist_rejects_unlisted_command(self):
        with pytest.raises(CommandValidationError) as exc:
            validate_command("git status", whitelist=["echo", "cat"])
        assert "not in whitelist" in exc.value.reason

    def test_whitelist_case_insensitive(self):
        validate_command("ECHO hello", whitelist=["echo"])

    def test_whitelist_still_blocks_blacklist_patterns(self):
        # Even whitelisted commands must pass blacklist checks
        with pytest.raises(CommandValidationError):
            validate_command("rm -rf /", whitelist=["rm"])

    def test_whitelist_empty_list_blocks_everything(self):
        with pytest.raises(CommandValidationError):
            validate_command("echo hello", whitelist=[])

    def test_whitelist_none_disables_whitelist_mode(self):
        # Default path (no whitelist) should allow normal commands
        validate_command("echo hello", whitelist=None)
