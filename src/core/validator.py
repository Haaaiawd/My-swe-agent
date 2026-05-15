"""CommandValidator: safety check before executing parsed shell commands.

Checks:
  1. Blacklist regex patterns (destructive commands like rm -rf /, dd, mkfs).
  2. Dangerous-flag + destructive-command combinations (e.g. rm -f).

Raises CommandValidationError on failure; returns None on success.

Dependencies: re, shlex; core.models.CommandValidationError.
Test coverage: tests/unit/test_validator.py.
"""

from __future__ import annotations

import os
import re
import shlex

from core.models import CommandValidationError

# ── Blacklist patterns ─────────────────────────────────────────
FORBIDDEN_PATTERNS: list[str] = [
    r"rm\s+-rf\s+/",
    r"dd\s+if=/dev/zero",
    r"mkfs\b",
    r"format\b",
    r":\(\)\{ :\|:\& };:",
]

# ── Destructive command + dangerous flag combos ─────────────────
DESTRUCTIVE_COMMANDS = {"rm", "mv", "dd", "shred", "mkfs"}
DANGEROUS_FLAGS = {"-f", "--force", "-rf", "--recursive"}


def validate_command(command: str, whitelist: list[str] | None = None) -> None:
    """Validate *command* for safety.  Raise CommandValidationError if unsafe.

    Args:
        command: The parsed shell command string.
        whitelist: Optional list of allowed command basenames.  When provided,
            only commands whose base name appears in the whitelist pass;
            everything else is rejected regardless of blacklist status.

    Raises:
        CommandValidationError: If the command is empty, not in the whitelist,
            matches a blacklist pattern, or combines a destructive command with
            a dangerous flag.
    """
    if not command or not command.strip():
        raise CommandValidationError(command, "Empty command")

    parts = shlex.split(command, posix=os.name != "nt")
    if not parts:
        raise CommandValidationError(command, "Empty command")

    cmd_base = parts[0].lower()

    # CH-R5-02: whitelist mode takes precedence
    if whitelist is not None:
        allowed = {w.lower() for w in whitelist}
        if cmd_base not in allowed:
            raise CommandValidationError(
                command,
                f"Command '{cmd_base}' not in whitelist",
            )
        # Even whitelisted commands are still subject to blacklist patterns

    # 1. Blacklist regex matching
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            raise CommandValidationError(
                command,
                f"Forbidden pattern matched: {pattern}",
            )

    # 2. Destructive command + dangerous flag combination
    if cmd_base in DESTRUCTIVE_COMMANDS:
        for flag in DANGEROUS_FLAGS:
            if flag in parts[1:]:
                raise CommandValidationError(
                    command,
                    f"Dangerous flag '{flag}' used with destructive command '{cmd_base}'",
                )
