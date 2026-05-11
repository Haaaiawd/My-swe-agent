"""TemplateRenderer: Jinja2 template rendering with StrictUndefined + observation truncation.

Core logic: compile and cache jinja2.Template (hash key), render with StrictUndefined,
truncate observations >= max_length to prefix+suffix.
Dependencies: jinja2, logging.
Edge cases: empty template -> empty string; undefined variable -> ConfigError;
max_length <= 0 -> ValueError; len < max_length -> passthrough.
Test coverage: tests/unit/test_config_renderer.py.
"""

from __future__ import annotations

import logging
from typing import Any

import jinja2

from config.exceptions import ConfigError

logger = logging.getLogger(__name__)

# ── Truncation constants (from config.detail.md §1.2) ───────────
DEFAULT_MAX_OBSERVATION_LENGTH = 10000
TRUNCATE_PREFIX_LENGTH = 5000
TRUNCATE_SUFFIX_LENGTH = 5000


class TemplateRenderer:
    """Jinja2 template renderer with template caching and observation truncation."""

    def __init__(self, jinja_env: jinja2.Environment) -> None:
        self.jinja_env = jinja_env
        self._template_cache: dict[int, jinja2.Template] = {}

    def render(self, template_content: str, context: dict[str, Any]) -> str:
        """Render *template_content* with *context* using StrictUndefined.

        Compiled templates are cached by ``hash(template_content)``.

        Raises:
            ConfigError: On undefined variable or template syntax error.
        """
        if not template_content:
            return ""

        try:
            cache_key = hash(template_content)
            template = self._template_cache.get(cache_key)
            if template is None:
                template = self.jinja_env.from_string(template_content)
                self._template_cache[cache_key] = template

            return template.render(**context)
        except jinja2.UndefinedError as e:
            raise ConfigError(
                f"Template rendering failed: undefined variable — {e}",
                variable=getattr(e, "name", None),
            ) from e
        except jinja2.TemplateSyntaxError as e:
            raise ConfigError(
                f"Template syntax error at line {e.lineno}: {e.message}",
                line=e.lineno,
            ) from e

    def truncate(self, output: str, max_length: int = DEFAULT_MAX_OBSERVATION_LENGTH) -> str:
        """Truncate *output* if its length is >= *max_length*.

        Truncation produces ``prefix + suffix`` where prefix length and
        suffix length are defined by ``TRUNCATE_PREFIX_LENGTH`` and
        ``TRUNCATE_SUFFIX_LENGTH``.

        Args:
            output: The string to potentially truncate.
            max_length: Threshold length; must be positive.

        Returns:
            The original string if shorter than *max_length*,
            otherwise a truncated version.

        Raises:
            ValueError: If *max_length* is not positive.
        """
        if max_length <= 0:
            raise ValueError(f"max_length must be positive, got {max_length}")
        if len(output) < max_length:
            return output

        elided = len(output) - max_length
        logger.warning(
            "Observation truncated, elided %d chars (original: %d)",
            elided,
            len(output),
        )
        return output[:TRUNCATE_PREFIX_LENGTH] + output[-TRUNCATE_SUFFIX_LENGTH:]
