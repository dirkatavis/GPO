from selenium.webdriver.common.by import By

from utils.logger import log
from utils.ui_helpers import find_element


class MVAInputPage:
    # Defensive locators for MVA input
    CANDIDATES = [
        (By.CSS_SELECTOR, "input.bp6-input[placeholder*='Enter MVA']"),
        (By.XPATH, "//input[@type='text' and contains(@placeholder,'MVA')]"),
        (
            By.XPATH,
            "//div[@role='tabpanel' and @aria-hidden='false']//input[@type='text']",
        ),
    ]

    def __init__(self, driver):
        self.driver = driver

    def find_input(self):
        """Return the active MVA input field by probing multiple locators."""
        for locator in self.CANDIDATES:
            try:
                return find_element(self.driver, locator, timeout=4)
            except Exception:
                continue

        log.info(f"[MVA_INPUT] No candidate locator matched — input field not found")
        return None  # swallow instead of raising
