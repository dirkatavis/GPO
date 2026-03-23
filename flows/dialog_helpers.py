from selenium.webdriver.common.by import By

from utils.logger import log
from utils.ui_helpers import find_element, find_elements, _dump_artifacts


def find_dialog(driver):
    """Return the main dialog container element."""
    log.debug("[DIALOG] Finding dialog.")
    locator = (By.CSS_SELECTOR, "div.bp6-dialog, div[class*='dialog']")
    return find_element(driver, locator)


def dbg_dialog(driver):
    """Debug: print dialog button labels and save screenshot."""
    log.debug("[DIALOG] Debugging dialog.")
    try:
        dlg = find_dialog(driver)
    except Exception:
        dlg = driver
    btns = dlg.find_elements(
        By.XPATH,
        ".//button//*[self::span or self::div or self::p or self::strong]|.//button",
    )
    labels = [b.text.strip() for b in btns if b.text.strip()]
    log.debug(f" dialog buttons -> {labels[:12]}")
    _dump_artifacts(driver, "debug_dialog")


def find_next_buttons(driver):
    """Return all 'Next' buttons currently visible in dialogs."""
    log.debug("[DIALOG] Finding next buttons.")
    locator = (
        By.XPATH,
        "//button[.//span[normalize-space()='Next'] or normalize-space()='Next']",
    )
    return find_elements(driver, locator, timeout=8)


def _dbg_dialog(driver):
    try:
        dlg = find_dialog(driver)
    except Exception:
        dlg = driver
    btns = dlg.find_elements(
        By.XPATH,
        ".//button//*[self::span or self::div or self::p or self::strong]|.//button",
    )
    labels = [b.text.strip() for b in btns if b.text.strip()]
    log.debug(f" dialog buttons -> {labels[:12]}")
    _dump_artifacts(driver, "debug_dialog")
