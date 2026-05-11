"""ConfigMerger: recursively merge configuration dictionaries.

Core logic: dict -> recursive merge; everything else (including list) -> override.
Dependencies: none (stdlib only).
Edge cases: None inputs are treated as empty dicts.
Test coverage: tests/unit/test_config_merger.py.
"""

from __future__ import annotations

from typing import Any


class ConfigMerger:
    """Recursively merge two configuration dictionaries."""

    def deep_merge(
        self,
        base: dict[str, Any] | None,
        override: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Merge *override* into *base*.

        Strategy:
          - dict values are merged recursively.
          - All other types (including list) are overridden.
          - ``None`` inputs are treated as empty dicts.

        Returns:
            A new dictionary containing the merged result.
        """
        if base is None and override is None:
            return {}

        base = base or {}
        override = override or {}
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self.deep_merge(result[key], value)
            else:
                result[key] = value

        return result
