import json
import logging
import os
from pathlib import Path

from config.config_loader import get_config

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

LOGIN_URL: str = get_config("login_url", "https://avisbudget.palantirfoundry.com/multipass/login")
SSO_EMAIL: str = get_config("credentials.sso_email", "")
STORAGE_STATE_PATH: Path = BASE_DIR / "storage_state.json"


def resolve_headless(config_path: Path | None = None) -> bool:
    """Check PLAYWRIGHT_HEADLESS env var first, then orchestrator_config.json, then default True."""
    env_val = os.getenv("PLAYWRIGHT_HEADLESS")
    if env_val is not None:
        result = env_val.strip().lower() not in ("0", "false", "no")
        log.info("Headless resolved from env PLAYWRIGHT_HEADLESS=%r → %s", env_val, result)
        return result

    path = config_path or (BASE_DIR / "orchestrator_config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "headless" in data:
            result = bool(data["headless"])
            log.info("Headless resolved from %s → %s", path.name, result)
            return result
    except (OSError, json.JSONDecodeError, ValueError):
        pass

    log.info("Headless defaulting to True")
    return True


def resolve_step_delay(config_path: Path | None = None) -> int:
    """Return inter-step delay in milliseconds.

    Priority: PLAYWRIGHT_STEP_DELAY env var (seconds) → orchestrator_config.local.json
    → orchestrator_config.json 'step_delay' key (seconds) → default 0.
    """
    env_val = os.getenv("PLAYWRIGHT_STEP_DELAY")
    if env_val is not None:
        try:
            result = int(float(env_val.strip()) * 1000)
            log.info("Step delay resolved from env PLAYWRIGHT_STEP_DELAY=%r → %dms", env_val, result)
            return result
        except ValueError:
            pass

    base_path = config_path or (BASE_DIR / "orchestrator_config.json")
    local_path = base_path.with_name(base_path.stem + ".local.json")

    data: dict = {}
    for path in (base_path, local_path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data.update(json.load(f))
        except (OSError, json.JSONDecodeError):
            pass

    if "step_delay" in data:
        try:
            result = int(float(data["step_delay"]) * 1000)
            log.info("Step delay resolved from config → %dms", result)
            return result
        except ValueError:
            pass

    return 0
