"""ConfigLoader: load configuration from multiple sources.

Core logic: YAML file (Jinja2 DebugUndefined then yaml.safe_load), env vars,
and hard-coded defaults.  Env vars use double-underscore nesting.
Dependencies: jinja2, yaml (pyyaml), os, re.
Boundaries: returns raw dicts; merging is ConfigMerger's job.
Edge cases: missing file -> FileNotFoundError; YAML/Jinja2 errors -> ConfigError.
Test coverage: tests/unit/test_config_loader.py.
"""

from __future__ import annotations

import copy
import logging
import os
import re
from typing import Any

import jinja2
import yaml

from config.exceptions import ConfigError

logger = logging.getLogger(__name__)

# ── Configuration constants (from config.detail.md §1) ──────────
DEFAULT_CONFIG: dict[str, Any] = {
    "model": {
        "name": "gpt-4o",
        "protocol": "tool-call",
        "api_key": None,
        "max_retries": 5,
        "cost_missing_strategy": "warn",
    },
    "executor": {
        "timeout": 120,
    },
    "agent": {
        "step_limit": 50,
        "cost_limit": 2.0,
        "cost_estimate_per_call": 0.05,
        "confirm_mode": True,
        "exit_immediately": False,
        "max_consecutive_format_errors": 5,
    },
    "output": {
        "trajectory_path": None,
        "observation_max_length": 10000,
        "observation_template": "{{ stdout }}",
    },
}


class ConfigLoader:
    """Load configuration from files, environment variables, and defaults."""

    def load_yaml_file(self, path: str) -> dict[str, Any]:
        """Read a YAML file: Jinja2 render (DebugUndefined) then yaml.safe_load.

        Args:
            path: Absolute or relative path to the YAML file.

        Returns:
            Parsed configuration dictionary.

        Raises:
            FileNotFoundError: If the file does not exist.
            ConfigError: On Jinja2 syntax / undefined variable or YAML parse error.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, encoding="utf-8") as f:
            raw = f.read()

        # Step 1: Jinja2 render with DebugUndefined for optional variables
        try:
            yaml_jinja_env = jinja2.Environment(undefined=jinja2.DebugUndefined)
            rendered = yaml_jinja_env.from_string(raw).render()
        except jinja2.TemplateSyntaxError as e:
            raise ConfigError(
                f"Jinja2 syntax error in {path}: {e}",
                file_path=path,
                line=e.lineno,
                variable=None,
            ) from e

        # Step 2: YAML parse
        try:
            result = yaml.safe_load(rendered)
        except yaml.YAMLError as e:
            error_msg = str(e)
            error_msg = _redact_sensitive(error_msg)
            raise ConfigError(
                f"YAML syntax error in {path}: {error_msg}",
                file_path=path,
                line=getattr(e, "problem_mark", None) and getattr(e.problem_mark, "line", None),
                variable=None,
            ) from e

        return result or {}

    def load_env_vars(self, prefix: str) -> dict[str, Any]:
        """Read environment variables starting with *prefix* into a nested dict.

        Conversion rules (example prefix="MINI_SWE"):
          MINI_SWE_MODEL__NAME=gpt-4o
            -> strip prefix -> MODEL__NAME=gpt-4o
            -> double-underscore split -> ["model", "name"]
            -> nested dict -> {"model": {"name": "gpt-4o"}}

        Keys are lower-cased. Values remain strings (consumed downstream).
        """
        if not prefix:
            return {}

        prefix_upper = prefix.upper() + "_"
        result: dict[str, Any] = {}

        for key, value in os.environ.items():
            if not key.upper().startswith(prefix_upper):
                continue

            stripped = key[len(prefix_upper) :]
            parts = [p.lower() for p in stripped.split("__") if p]
            if not parts:
                continue

            node = result
            for part in parts[:-1]:
                if part not in node or not isinstance(node[part], dict):
                    node[part] = {}
                node = node[part]
            node[parts[-1]] = value

        return result

    def load_defaults(self) -> dict[str, Any]:
        """Return the hard-coded default configuration dictionary."""
        # Return a deep copy so callers cannot mutate nested structures
        return copy.deepcopy(DEFAULT_CONFIG)


def _redact_sensitive(text: str) -> str:
    """Redact sensitive patterns in error messages."""
    # Redact api_key/password/token/secret followed by = or : and a value
    text = re.sub(
        r"(api[_-]?key|password|token|secret)\s*[=:]\s*\S+",
        r"\1=***",
        text,
        flags=re.IGNORECASE,
    )
    # Redact sk-... OpenAI key patterns
    text = re.sub(r"sk-[A-Za-z0-9]{20,}", "***", text)
    return text
