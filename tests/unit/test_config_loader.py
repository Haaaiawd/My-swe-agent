"""Unit tests for ConfigLoader.

Covers: YAML normal/ syntax error / missing file; env prefix nesting; defaults return.
"""

from __future__ import annotations

import pytest

from config.exceptions import ConfigError
from config.loader import ConfigLoader


class TestLoadYamlFile:
    def test_valid_yaml_with_jinja2(self, tmp_path):
        loader = ConfigLoader()
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text('model:\n  name: "{{ model_name }}"\n', encoding="utf-8")

        result = loader.load_yaml_file(str(yaml_path))
        assert result == {"model": {"name": "{{ model_name }}"}}

    def test_valid_yaml_no_jinja(self, tmp_path):
        loader = ConfigLoader()
        yaml_path = tmp_path / "test.yaml"
        yaml_path.write_text("executor:\n  timeout: 60\n", encoding="utf-8")

        result = loader.load_yaml_file(str(yaml_path))
        assert result == {"executor": {"timeout": 60}}

    def test_missing_file(self):
        loader = ConfigLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_yaml_file("/nonexistent/path.yaml")

    def test_yaml_syntax_error(self, tmp_path):
        loader = ConfigLoader()
        yaml_path = tmp_path / "bad.yaml"
        yaml_path.write_text("executor: timeout: 60\n", encoding="utf-8")

        with pytest.raises(ConfigError) as exc_info:
            loader.load_yaml_file(str(yaml_path))
        assert "YAML syntax error" in str(exc_info.value)

    def test_jinja2_undefined_variable(self, tmp_path):
        loader = ConfigLoader()
        yaml_path = tmp_path / "bad.yaml"
        yaml_path.write_text("model:\n  name: " + "{{ undefined_var }}\n", encoding="utf-8")

        # DebugUndefined does not raise during render, but yaml.safe_load
        # fails on the unresolvable placeholder -> wrapped as ConfigError.
        with pytest.raises(ConfigError) as exc_info:
            loader.load_yaml_file(str(yaml_path))
        assert "YAML syntax error" in str(exc_info.value)

    def test_empty_file(self, tmp_path):
        loader = ConfigLoader()
        yaml_path = tmp_path / "empty.yaml"
        yaml_path.write_text("", encoding="utf-8")

        result = loader.load_yaml_file(str(yaml_path))
        assert result == {}


class TestLoadEnvVars:
    def test_prefix_nesting(self, monkeypatch):
        monkeypatch.setenv("MINI_SWE_MODEL__NAME", "gpt-4")
        loader = ConfigLoader()
        result = loader.load_env_vars("MINI_SWE")
        assert result == {"model": {"name": "gpt-4"}}

    def test_deep_nesting(self, monkeypatch):
        monkeypatch.setenv("MINI_SWE_AGENT__STEP_LIMIT", "30")
        loader = ConfigLoader()
        result = loader.load_env_vars("MINI_SWE")
        assert result == {"agent": {"step_limit": "30"}}

    def test_no_match(self, monkeypatch):
        monkeypatch.setenv("OTHER_VAR", "value")
        loader = ConfigLoader()
        result = loader.load_env_vars("MINI_SWE")
        assert result == {}

    def test_empty_prefix(self):
        loader = ConfigLoader()
        result = loader.load_env_vars("")
        assert result == {}


class TestLoadDefaults:
    def test_returns_dict(self):
        loader = ConfigLoader()
        result = loader.load_defaults()
        assert isinstance(result, dict)
        assert result["model"]["name"] == "gpt-4o"
        assert result["agent"]["step_limit"] == 50

    def test_isolation(self):
        loader = ConfigLoader()
        result1 = loader.load_defaults()
        result1["model"]["name"] = "mutated"
        result2 = loader.load_defaults()
        assert result2["model"]["name"] == "gpt-4o"
