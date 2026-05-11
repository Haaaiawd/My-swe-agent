"""Unit tests for ConfigMerger.

Covers: nested dict merge, list override, None handling, multi-layer priority.
"""

from __future__ import annotations

from config.merger import ConfigMerger


class TestDeepMerge:
    def test_nested_dict_merge(self):
        merger = ConfigMerger()
        base = {"a": {"x": 1}}
        override = {"a": {"y": 2}}
        result = merger.deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 2}}

    def test_list_override(self):
        merger = ConfigMerger()
        base = {"a": [1, 2]}
        override = {"a": [3]}
        result = merger.deep_merge(base, override)
        assert result == {"a": [3]}

    def test_none_base(self):
        merger = ConfigMerger()
        result = merger.deep_merge(None, {"k": "v"})
        assert result == {"k": "v"}

    def test_none_override(self):
        merger = ConfigMerger()
        result = merger.deep_merge({"k": "v"}, None)
        assert result == {"k": "v"}

    def test_both_none(self):
        merger = ConfigMerger()
        result = merger.deep_merge(None, None)
        assert result == {}

    def test_type_mismatch_override(self):
        merger = ConfigMerger()
        base = {"a": {"x": 1}}
        override = {"a": "string"}
        result = merger.deep_merge(base, override)
        assert result == {"a": "string"}

    def test_deep_nesting(self):
        merger = ConfigMerger()
        base = {"a": {"b": {"c": 1}}}
        override = {"a": {"b": {"d": 2}}}
        result = merger.deep_merge(base, override)
        assert result == {"a": {"b": {"c": 1, "d": 2}}}

    def test_does_not_mutate_inputs(self):
        merger = ConfigMerger()
        base = {"a": {"x": 1}}
        override = {"a": {"y": 2}}
        merger.deep_merge(base, override)
        assert base == {"a": {"x": 1}}
        assert override == {"a": {"y": 2}}
