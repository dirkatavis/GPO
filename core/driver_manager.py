import subprocess
import re
import os
import winreg
import logging
from selenium import webdriver
from selenium.common.exceptions import SessionNotCreatedException
from selenium.webdriver.edge.service import Service

import os
# ...
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DRIVER_PATH = os.path.join(PROJECT_ROOT, "msedgedriver.exe")
# Logger
log = logging.getLogger("mc.automation")

_driver = None  # singleton instance






def get_browser_version() -> str:
    """Return installed Edge browser version from Windows registry."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Edge\BLBeacon")
        value, _ = winreg.QueryValueEx(key, "version")
        return value
    except Exception as e:
        print(f"Error: {e}")
        return "unknown"
if __name__ == "__main__":
    print("Edge Browser Version:", get_browser_version())










def get_driver_version(driver_path: str) -> str:
    """Return Edge WebDriver version (e.g., 140.0.x.x)."""
    if not os.path.exists(driver_path):
        log.error(f"[DRIVER] Driver binary not found at {driver_path}")
        return "unknown"
    try:
        output = subprocess.check_output([driver_path, "--version"], text=True)
        return re.search(r"(\d+\.\d+\.\d+\.\d+)", output).group(1)
    except Exception as e:
        log.error(f"[DRIVER] Failed to get driver version from {driver_path} - {e}")
        return "unknown"



def create_driver():
    """Create a new Edge WebDriver. Raises error if driver already exists."""
    global _driver
    if _driver:
        raise RuntimeError("WebDriver already exists. Call quit_driver() before creating a new one.")

    browser_ver = get_browser_version()
    driver_ver = get_driver_version(DRIVER_PATH)
    log.info(f"[DRIVER] Detected Browser={browser_ver}, Driver={driver_ver}")
    if browser_ver.split(".")[0] != driver_ver.split(".")[0]:
        log.error(f"[DRIVER] Version mismatch - Browser {browser_ver}, Driver {driver_ver}")
        raise RuntimeError("Edge/Driver version mismatch")
    try:
        log.info(f"[DRIVER] Launching Edge - Browser {browser_ver}, Driver {driver_ver}")
        options = webdriver.EdgeOptions()
        options.add_argument("--start-maximized")
        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.geolocation": 2 })
        service = Service(DRIVER_PATH)
        _driver = webdriver.Edge(service=service, options=options)
        return _driver
    except SessionNotCreatedException as e:
        log.error(f"[DRIVER] Session creation failed: {e}")
        raise


def get_driver():
    """Return the existing Edge WebDriver, or raise error if not created."""
    global _driver
    if not _driver:
        raise RuntimeError("WebDriver does not exist. Call create_driver() first.")
    return _driver


def quit_driver():
    """Quit and reset the singleton driver."""
    global _driver
    if _driver:
        log.info("[DRIVER] Quitting Edge WebDriver...")
        _driver.quit()
        _driver = None
