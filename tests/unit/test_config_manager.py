"""Unit tests for ConfigManager.

Covers: redaction (api_key/token/secret/nested), multi-source merge priority,
cache clear, template rendering delegation, truncation delegation.
"""

from __future__ import annotations

import pytest

from config.config_manager import ConfigManager
from config.exceptions import ConfigError


class TestRedaction:
    def test_api_key_redacted_in_repr(self):
        cm = ConfigManager()
        cm._config_cache = {"model": {"api_key": "sk-abc", "name": "gpt-4o"}}
        rep = repr(cm)
        assert "***" in rep
        assert "sk-abc" not in rep

    def test_nested_secret_redacted(self):
        cm = ConfigManager()
        cm._config_cache = {"deep": {"password": "secret123"}}
        rep = repr(cm)
        assert "secret123" not in rep
        assert "***" in rep

    def test_non_sensitive_fields_preserved(self):
        cm = ConfigManager()
        cm._config_cache = {"model": {"name": "gpt-4o", "max_retries": 5}}
        rep = repr(cm)
        assert "gpt-4o" in rep

    def test_list_redaction(self):
        cm = ConfigManager()
        cm._config_cache = {"items": [{"token": "tk-xxx"}, {"name": "ok"}]}
        rep = repr(cm)
        assert "tk-xxx" not in rep
        assert "ok" in rep


class TestLoadConfigPriority:
    def test_defaults_loaded(self):
        cm = ConfigManager()
        config = cm.load_config()
        assert config["model"]["name"] == "gpt-4o"
        assert config["agent"]["step_limit"] == 50

    def test_cli_overrides_default(self):
        cm = ConfigManager()
        config = cm.load_config(cli_args={"model": {"name": "gpt-3.5"}})
        assert config["model"]["name"] == "gpt-3.5"

    def test_file_overrides_default(self, tmp_path):
        cm = ConfigManager()
        yaml_path = tmp_path / "cfg.yaml"
        yaml_path.write_text("agent:\n  step_limit: 30\n", encoding="utf-8")
        config = cm.load_config(config_paths=[str(yaml_path)])
        assert config["agent"]["step_limit"] == 30

    def test_cli_overrides_file(self, tmp_path):
        cm = ConfigManager()
        yaml_path = tmp_path / "cfg.yaml"
        yaml_path.write_text("agent:\n  step_limit: 30\n", encoding="utf-8")
        config = cm.load_config(
            config_paths=[str(yaml_path)],
            cli_args={"agent": {"step_limit": 10}},
        )
        assert config["agent"]["step_limit"] == 10

    def test_env_overrides_default(self, monkeypatch):
        monkeypatch.setenv("MINI_SWE_MODEL__NAME", "claude-3")
        cm = ConfigManager()
        config = cm.load_config(env_prefix="MINI_SWE")
        assert config["model"]["name"] == "claude-3"

    def test_file_overrides_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MINI_SWE_MODEL__NAME", "claude-3")
        cm = ConfigManager()
        yaml_path = tmp_path / "cfg.yaml"
        yaml_path.write_text("model:\n  name: gpt-4o\n", encoding="utf-8")
        config = cm.load_config(
            config_paths=[str(yaml_path)],
            env_prefix="MINI_SWE",
        )
        assert config["model"]["name"] == "gpt-4o"

    def test_multi_file_later_wins(self, tmp_path):
        cm = ConfigManager()
        p1 = tmp_path / "a.yaml"
        p1.write_text("agent:\n  step_limit: 10\n", encoding="utf-8")
        p2 = tmp_path / "b.yaml"
        p2.write_text("agent:\n  step_limit: 20\n", encoding="utf-8")
        config = cm.load_config(config_paths=[str(p1), str(p2)])
        assert config["agent"]["step_limit"] == 20

    def test_missing_file_raises(self):
        cm = ConfigManager()
        with pytest.raises(FileNotFoundError):
            cm.load_config(config_paths=["/nonexistent.yaml"])


class TestCache:
    def test_clear_cache(self):
        cm = ConfigManager()
        cm.load_config(cli_args={"x": 1})
        cm.clear_cache()
        assert cm._config_cache == {}
        assert cm._renderer._template_cache == {}


class TestRenderTemplate:
    def test_delegates_to_renderer(self):
        cm = ConfigManager()
        result = cm.render_template("Hello {{ name }}!", {"name": "World"})
        assert result == "Hello World!"

    def test_undefined_raises(self):
        cm = ConfigManager()
        with pytest.raises(ConfigError):
            cm.render_template("{{ undefined }}", {})


class TestTruncateObservation:
    def test_short_passthrough(self):
        cm = ConfigManager()
        assert cm.truncate_observation("hello") == "hello"

    def test_truncation(self):
        cm = ConfigManager()
        long_str = "x" * 10001
        result = cm.truncate_observation(long_str)
        assert len(result) == 10000
