from __future__ import annotations

import time
from typing import Tuple

from .base_page import BasePage

try:
    from selenium.webdriver.common.by import By
except Exception:

    class _By:
        CSS_SELECTOR = "css selector"
        XPATH = "xpath"
        ID = "id"
        NAME = "name"

    By = _By()  # type: ignore


class DrivabilityPage(BasePage):
    class S:
        DIALOG: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "div.bp6-dialog[data-testid='drivability-page'], div.fleet-operations-pwa__drivabilityPage",
        )
        # Use the container and the H1 text the page actually renders
        YES_BTN = (
            By.XPATH,
            "//div[contains(@class,'drivable-options-container')]//button[.//h1[normalize-space()='Yes']]",
        )
        NO_BTN = (
            By.XPATH,
            "//div[contains(@class,'drivable-options-container')]//button[.//h1[normalize-space()='No']]",
        )
        NEXT_BTN: Tuple[str, str] = (
            By.XPATH,
            "//h1[normalize-space()='Is vehicle drivable?']"
            "/ancestor::div[contains(@class,'drivable-header-container')]"
            "/following::button[.//span[normalize-space()='Next'] or normalize-space()='Next'][1]",
        )

    def ensure_open(self) -> None:
        self.find(By.XPATH, "//h1[normalize-space()='Is vehicle drivable?']")

    def select_drivable(self, drivable: bool) -> None:
        btn = self.S.YES_BTN if drivable else self.S.NO_BTN
        self.find(*btn).click()
        time.sleep(0.3)

    def click_next(self) -> None:
        self.find(*self.S.NEXT_BTN).click()
        time.sleep(0.5)


def has_next_button(self) -> bool:
    """Return True if the Next button is visible on the drivability page."""
    return bool(self.driver.find_elements(*self.S.NEXT_BTN))
