# FILE: pages/mileage_dialog.py
# PASTE THIS FULL FILE

from __future__ import annotations

from typing import Tuple

from utils.ui_helpers import click_element_by_text

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


class MileageDialog(BasePage):
    """Represents the Mileage entry dialog in the Work Item flow."""

    # ---- Selector constants -------------------------------------------------
    class S:
        DIALOG: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "div.bp6-dialog[data-testid='mileage-dialog'], div.fleet-operations-pwa__mileageDialog",
        )
        INPUT: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "input[data-testid='mileage-input'], input.fleet-operations-pwa__mileageInput",
        )
        NEXT_BTN: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "button[data-testid='mileage-next'], button.bp6-button.bp6-intent-primary",
        )

    # ---- Public API (stubs) ------------------------------------------------
    def ensure_open(self) -> None:
        """Later: wait until dialog S.DIALOG is visible."""
        pass

    def enter_mileage(self, value: str) -> None:
        """Stub: type mileage into input."""
        pass

    def click_next(self) -> bool:
        """Click the 'Next' button to advance from the mileage dialog."""
        return click_element_by_text(self.driver, tag="button", text="Next")

    def has_next_button(self) -> bool:
        """Return True if the Next button is visible on the mileage dialog."""
        return bool(self.driver.find_elements(*self.S.NEXT_BTN))
