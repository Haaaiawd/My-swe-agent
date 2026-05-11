"""ConfigManager: top-level composition of Loader + Merger + Renderer.

Core logic: multi-source config loading (defaults -> env -> files -> CLI args),
recursive merge, template rendering, observation truncation, and sensitive-field
redaction for safe logging.
Dependencies: jinja2, config.loader, config.merger, config.renderer, config.exceptions.
Boundaries: consumed by CLI and Core Agent Systems.
Edge cases: empty inputs, missing files, undefined template variables.
Test coverage: tests/unit/test_config_manager.py.
"""

from __future__ import annotations

from typing import Any

import jinja2

from config.loader import ConfigLoader
from config.merger import ConfigMerger
from config.renderer import (
    DEFAULT_MAX_OBSERVATION_LENGTH,
    TemplateRenderer,
)


class ConfigManager:
    """Configuration manager: unified entry-point for load, merge, render, truncate.

    Safety: ``repr()`` and ``__str__`` automatically redact sensitive fields
    (api_key, password, token, secret) to prevent credential leakage in logs.
    """

    # Sensitive keys redacted in repr/logs
    SENSITIVE_KEYS: frozenset[str] = frozenset({"api_key", "password", "token", "secret"})

    def __init__(self) -> None:
        self.jinja_env = jinja2.Environment(
            undefined=jinja2.StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._loader = ConfigLoader()
        self._merger = ConfigMerger()
        self._renderer = TemplateRenderer(self.jinja_env)
        self._config_cache: dict[str, Any] = {}
        self._template_cache: dict[str, jinja2.Template] = {}

    # ── Redaction ───────────────────────────────────────────────

    def _redact(self, obj: Any) -> Any:
        """Recursively redact sensitive string values to '***'."""
        if isinstance(obj, dict):
            return {
                k: "***" if k in self.SENSITIVE_KEYS and isinstance(v, str) else self._redact(v)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [self._redact(item) for item in obj]
        return obj

    def __repr__(self) -> str:
        return f"ConfigManager(config={self._redact(self._config_cache)})"

    # ── Public API ──────────────────────────────────────────────

    def load_config(
        self,
        config_paths: list[str] | None = None,
        cli_args: dict[str, Any] | None = None,
        env_prefix: str | None = None,
    ) -> dict[str, Any]:
        """Load and merge configuration from multiple sources.

        Priority (low -> high): defaults -> env vars -> files (in order) -> CLI args.

        Args:
            config_paths: List of YAML file paths to load and merge.
            cli_args: Dictionary of CLI override arguments.
            env_prefix: Environment variable prefix (e.g. "MINI_SWE").

        Returns:
            Merged configuration dictionary.

        Raises:
            FileNotFoundError: If a config file does not exist.
            ConfigError: On YAML / Jinja2 parse or render error.
        """
        # Step 1: defaults
        config = self._loader.load_defaults()

        # Step 2: environment variables
        if env_prefix:
            env_config = self._loader.load_env_vars(env_prefix)
            config = self._merger.deep_merge(config, env_config)

        # Step 3: configuration files (later files win)
        for path in config_paths or []:
            file_config = self._loader.load_yaml_file(path, self._renderer)
            config = self._merger.deep_merge(config, file_config)

        # Step 4: CLI args (highest priority)
        if cli_args:
            config = self._merger.deep_merge(config, cli_args)

        self._config_cache = config
        return config

    def render_template(
        self,
        template_content: str,
        context: dict[str, Any],
    ) -> str:
        """Render *template_content* with *context* using StrictUndefined."""
        return self._renderer.render(template_content, context)

    def truncate_observation(
        self,
        output: str,
        max_length: int = DEFAULT_MAX_OBSERVATION_LENGTH,
    ) -> str:
        """Truncate *output* if its length exceeds *max_length*."""
        return self._renderer.truncate(output, max_length)

    def clear_cache(self) -> None:
        """Clear the configuration and template caches."""
        self._config_cache.clear()
        self._renderer._template_cache.clear()

    def _load_defaults(self) -> dict[str, Any]:
        """Return the hard-coded default configuration."""
        return self._loader.load_defaults()
