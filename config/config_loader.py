import json
import os
from typing import Any

# Path to config.json in the same folder
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

# Load once at import
try:
    with open(CONFIG_PATH, "r") as f:
        _CONFIG = json.load(f)
except FileNotFoundError:
    raise RuntimeError(f"[CONFIG] Missing file: {CONFIG_PATH}")
except json.JSONDecodeError as e:
    raise RuntimeError(f"[CONFIG] Invalid JSON format in {CONFIG_PATH}: {e}")


def get_config(key: str, default: Any = None) -> Any:
    """
    Retrieve a config value by key.

    Args:
        key: The key to look up in config.json
        default: Optional fallback if key is missing

    Returns:
        The value from config.json or the default if provided.
    """
    if key not in _CONFIG and default is None:
        raise KeyError(f"[CONFIG] Missing key: '{key}' in {CONFIG_PATH}")
    return _CONFIG.get(key, default)

DEFAULT_TIMEOUT = _CONFIG.get("delay_seconds", 8)
