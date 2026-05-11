"""Config System — multi-source configuration management.

Public API:
    ConfigManager: unified entry-point for load, merge, render, truncate.
    ConfigError: base exception for configuration errors.
"""

from __future__ import annotations

from config.config_manager import ConfigManager
from config.exceptions import ConfigError

__all__ = ["ConfigManager", "ConfigError"]
