"""
ConfigManager — stores user configuration locally.
Config file: ~/.worklens/config.json
Never committed to git.
"""
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
CONFIG_PATH = Path.home() / ".worklens" / "config.json"


class ConfigManager:
    """Simple local config stored in ~/.worklens/config.json."""

    def __init__(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()
        logger.debug(f"Config updated: {key}")

    def has(self, key: str) -> bool:
        return key in self._data and bool(self._data[key])

    def _load(self) -> dict:
        if CONFIG_PATH.exists():
            try:
                return json.loads(CONFIG_PATH.read_text())
            except Exception as e:
                logger.error(f"Config load error: {e}")
        return {}

    def _save(self) -> None:
        try:
            CONFIG_PATH.write_text(json.dumps(self._data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Config save error: {e}")
