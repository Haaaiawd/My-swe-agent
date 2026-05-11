"""Unit tests for TemplateRenderer.

Covers: StrictUndefined trigger, normal rendering, truncation boundaries.
"""

from __future__ import annotations

import logging

import jinja2
import pytest

from config.exceptions import ConfigError
from config.renderer import (
    TRUNCATE_PREFIX_LENGTH,
    TRUNCATE_SUFFIX_LENGTH,
    TemplateRenderer,
)


class TestRender:
    def test_undefined_variable_raises(self):
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        renderer = TemplateRenderer(env)
        with pytest.raises(ConfigError) as exc_info:
            renderer.render("{{ undefined_var }}", {})
        assert "undefined variable" in str(exc_info.value).lower()

    def test_normal_render(self):
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        renderer = TemplateRenderer(env)
        result = renderer.render("Hello {{ name }}!", {"name": "World"})
        assert result == "Hello World!"

    def test_empty_template(self):
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        renderer = TemplateRenderer(env)
        result = renderer.render("", {})
        assert result == ""

    def test_template_syntax_error(self):
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        renderer = TemplateRenderer(env)
        with pytest.raises(ConfigError) as exc_info:
            renderer.render("{% if %}", {})
        assert "syntax error" in str(exc_info.value).lower()

    def test_template_caching(self):
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        renderer = TemplateRenderer(env)
        template = "Hello {{ name }}!"
        renderer.render(template, {"name": "A"})
        renderer.render(template, {"name": "B"})
        assert len(renderer._template_cache) == 1


class TestTruncate:
    def test_below_threshold_no_truncation(self):
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        renderer = TemplateRenderer(env)
        output = "x" * 9999
        result = renderer.truncate(output)
        assert result == output

    def test_at_threshold_truncation(self, caplog):
        """ADR-004: output length >= 10000 triggers truncation."""
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        renderer = TemplateRenderer(env)
        output = "x" * 10000
        result = renderer.truncate(output)
        assert len(result) == TRUNCATE_PREFIX_LENGTH + TRUNCATE_SUFFIX_LENGTH
        assert "elided 0 chars" in caplog.text

    def test_above_threshold_truncation(self, caplog):
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        renderer = TemplateRenderer(env)
        output = "x" * 10001
        with caplog.at_level(logging.WARNING):
            result = renderer.truncate(output)
        assert len(result) == TRUNCATE_PREFIX_LENGTH + TRUNCATE_SUFFIX_LENGTH
        assert result == "x" * TRUNCATE_PREFIX_LENGTH + "x" * TRUNCATE_SUFFIX_LENGTH
        assert "elided 1 chars" in caplog.text

    def test_max_length_zero_raises(self):
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        renderer = TemplateRenderer(env)
        with pytest.raises(ValueError):
            renderer.truncate("hello", max_length=0)

    def test_empty_output(self):
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        renderer = TemplateRenderer(env)
        result = renderer.truncate("")
        assert result == ""
