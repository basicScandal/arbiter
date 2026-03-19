"""Plugin discovery and loading for Arbiter.

Scans a ``plugins/`` directory (relative to the project root, or overridden
via ``ARBITER_PLUGINS_DIR`` environment variable) for YAML config files and
exposes them as :class:`PluginConfig` instances.

Typical usage::

    from src.plugins import discover_plugins, load_plugin

    # Auto-discover all plugins in the default directory
    configs = discover_plugins()

    # Load a single plugin by path
    cfg = load_plugin("plugins/my-event.yaml")
    rubric = cfg.get_rubric()
    persona = cfg.get_persona_prompt()
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.plugins.loader import PluginConfig, load_plugin

__all__ = ["PluginConfig", "load_plugin", "discover_plugins"]

logger = logging.getLogger(__name__)

# Project root is two levels up from this file (src/plugins/__init__.py)
_PROJECT_ROOT = Path(__file__).parent.parent.parent


def _plugins_dir() -> Path:
    """Return the plugins directory, respecting ``ARBITER_PLUGINS_DIR`` env var."""
    env_override = os.environ.get("ARBITER_PLUGINS_DIR")
    if env_override:
        return Path(env_override)
    return _PROJECT_ROOT / "plugins"


def discover_plugins() -> list[PluginConfig]:
    """Scan the plugins directory and return all successfully loaded configs.

    Files that fail validation are logged as warnings and skipped rather than
    raising, so a broken plugin cannot prevent the rest from loading.

    Returns:
        List of :class:`PluginConfig` instances, one per valid YAML file found.
        Empty list if the plugins directory does not exist.
    """
    directory = _plugins_dir()
    if not directory.exists():
        logger.debug("Plugins directory %s does not exist, skipping discovery", directory)
        return []

    configs: list[PluginConfig] = []
    yaml_files = sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml"))

    for path in yaml_files:
        try:
            cfg = load_plugin(str(path))
            configs.append(cfg)
            logger.info("Loaded plugin %r from %s", cfg.event_name, path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load plugin from %s: %s", path, exc)

    return configs
