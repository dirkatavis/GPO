import json
import os
from typing import Any

CONFIG_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
LOCAL_CONFIG_PATH = os.path.join(CONFIG_DIR, "config.local.json")


def _load_json_config(path: str, required: bool) -> dict[str, Any]:
    """Load a JSON config file and return a dict payload."""
    try:
        with open(path, "r", encoding="utf-8") as config_file:
            loaded = json.load(config_file)
    except FileNotFoundError:
        if required:
            raise RuntimeError(f"[CONFIG] Missing file: {path}") from None
        return {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"[CONFIG] Invalid JSON format in {path}: {exc}") from exc

    if not isinstance(loaded, dict):
        raise RuntimeError(f"[CONFIG] Expected object at root of {path}")
    return loaded


def _merge_dicts(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override values into a base config dict."""
    merged = dict(base)
    for key, value in overrides.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(value, dict):
            merged[key] = _merge_dicts(base_value, value)
        else:
            merged[key] = value
    return merged


def _get_nested_value(config: dict[str, Any], key: str) -> Any:
    """Resolve a dotted config key like credentials.sso_email."""
    current: Any = config
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(part)
        current = current[part]
    return current


_CONFIG = _merge_dicts(
    _load_json_config(CONFIG_PATH, required=True),
    _load_json_config(LOCAL_CONFIG_PATH, required=False),
)


def get_config(key: str, default: Any = None) -> Any:
    """Retrieve a config value by key, supporting dotted paths and local overrides."""
    try:
        return _get_nested_value(_CONFIG, key)
    except KeyError:
        if default is None:
            raise KeyError(f"[CONFIG] Missing key: '{key}' in {CONFIG_PATH}") from None
        return default


DEFAULT_TIMEOUT = int(get_config("delay_seconds", 8))
