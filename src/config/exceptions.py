"""Config System exceptions.

Core logic: configuration-related error base class with diagnostic attributes.
Dependencies: none (stdlib only).
Boundaries: raised by ConfigLoader, TemplateRenderer; caught by CLI and Core Agent.
Test coverage: tests/unit/test_config_loader.py, tests/unit/test_config_renderer.py.
"""

from __future__ import annotations


class ConfigError(RuntimeError):
    """Base exception for configuration management errors.

    Attributes:
        message: User-friendly error description.
        file_path: Path to the file triggering the error (if applicable).
        line: Line number where template rendering failed (if applicable).
        variable: Undefined variable name (if applicable).
    """

    def __init__(
        self,
        message: str,
        *,
        file_path: str | None = None,
        line: int | None = None,
        variable: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.file_path = file_path
        self.line = line
        self.variable = variable
