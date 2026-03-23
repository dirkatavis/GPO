import logging
import os
import re
import subprocess
import winreg

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.edge.service import Service

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DRIVER_PATH = os.path.join(PROJECT_ROOT, "msedgedriver.exe")
log = logging.getLogger("mc.automation")

_STATE = {"driver": None}


def get_browser_version() -> str:
    """Return installed Edge browser version from Windows registry."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Edge\BLBeacon")
        value, _ = winreg.QueryValueEx(key, "version")
        return value
    except OSError as exc:
        log.warning("[DRIVER] Failed to read Edge browser version: %s", exc)
        return "unknown"


def get_driver_version(driver_path: str) -> str:
    """Return Edge WebDriver version (e.g., 140.0.x.x)."""
    if not os.path.exists(driver_path):
        log.warning("[DRIVER] Bundled driver not found at %s (fallback unavailable)", driver_path)
        return "unknown"

    try:
        output = subprocess.check_output([driver_path, "--version"], text=True)
        match = re.search(r"(\d+\.\d+\.\d+\.\d+)", output)
        return match.group(1) if match else "unknown"
    except (OSError, subprocess.SubprocessError) as exc:
        log.error("[DRIVER] Failed to get driver version from %s - %s", driver_path, exc)
        return "unknown"


def _major_version(version: str) -> str | None:
    """Return major version (e.g. '146') from a full semantic version."""
    match = re.match(r"(\d+)\.", version)
    return match.group(1) if match else None


def _build_edge_options() -> webdriver.EdgeOptions:
    """Build edge options used for both managed and bundled launches."""
    options = webdriver.EdgeOptions()
    headless_enabled = os.getenv("CGI_HEADLESS", "0").strip().lower() in {"1", "true", "yes", "on"}
    if headless_enabled:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        log.info("[DRIVER] Headless mode enabled via CGI_HEADLESS")
    else:
        options.add_argument("--start-maximized")

    options.add_experimental_option(
        "prefs",
        {"profile.default_content_setting_values.geolocation": 2},
    )
    return options


def _launch_edge(options: webdriver.EdgeOptions, service: Service | None = None):
    """Launch Edge with optional explicit service."""
    if service is None:
        return webdriver.Edge(options=options)
    return webdriver.Edge(service=service, options=options)


def create_driver():
    """Create a new Edge WebDriver. Raises error if driver already exists."""
    if _STATE["driver"]:
        raise RuntimeError("WebDriver already exists. Call quit_driver() before creating a new one.")

    browser_ver = get_browser_version()
    options = _build_edge_options()

    log.info("[DRIVER] Launching Edge via Selenium Manager (Browser %s)", browser_ver)
    try:
        _STATE["driver"] = _launch_edge(options)
        return _STATE["driver"]
    except (WebDriverException, OSError) as exc:
        log.warning(
            "[DRIVER] Selenium Manager failed (%s). Trying bundled driver as fallback.",
            exc,
        )

    driver_ver = get_driver_version(DRIVER_PATH)
    log.info("[DRIVER] Fallback check - Browser=%s, bundled Driver=%s", browser_ver, driver_ver)
    browser_major = _major_version(browser_ver)
    driver_major = _major_version(driver_ver)
    if browser_major and driver_major and browser_major == driver_major:
        log.info("[DRIVER] Bundled driver version matches - attempting launch.")
        _STATE["driver"] = _launch_edge(options, service=Service(DRIVER_PATH))
        return _STATE["driver"]

    raise RuntimeError(
        f"Edge driver could not be started. Selenium Manager unavailable and bundled "
        f"driver is stale (Browser {browser_ver}, bundled Driver {driver_ver}). "
        f"Ensure network access so Selenium Manager can download a matching driver."
    )


def get_driver():
    """Return the existing Edge WebDriver, or raise error if not created."""
    if not _STATE["driver"]:
        raise RuntimeError("WebDriver does not exist. Call create_driver() first.")
    return _STATE["driver"]


def quit_driver():
    """Quit and reset the singleton driver."""
    if _STATE["driver"]:
        log.info("[DRIVER] Quitting Edge WebDriver...")
        _STATE["driver"].quit()
        _STATE["driver"] = None
