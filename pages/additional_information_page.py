# FILE: pages/additional_info_page.py
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


class AdditionalInfoPage(BasePage):
    """Represents the Additional Information step in the Work Item flow."""

    # ---- Selector constants -------------------------------------------------
    class S:
        DIALOG: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "div.bp6-dialog[data-testid='additional-info-page'], div.fleet-operations-pwa__additionalInfoPage",
        )
        # Generic inputs (labels + fields pattern; refine when DOM is known)
        TEXT_INPUT: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "input[type='text'], textarea",
        )
        TOGGLE_INPUT: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "input[type='checkbox'], div[role='switch']",
        )
        NEXT_BTN: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "button[data-testid='additional-info-next'], button.bp6-button.bp6-intent-primary",
        )

    # ---- Public API (stubs) ------------------------------------------------
    def ensure_open(self) -> None:
        """Later: wait until S.DIALOG is visible."""
        pass

    def set_text(self, label_text: str, value: str) -> None:
        """
        Stub: find a text field by its label and type value.
        Example: set_text('Notes', 'Customer reported vibration at idle.')
        """
        pass

    def set_toggle(self, label_text: str, on: bool) -> None:
        """
        Stub: find a toggle/checkbox by its label and set True/False.
        Example: set_toggle('Requires Tow', False)
        """
        pass

    def click_next(self) -> None:
        """Stub: advance to the Mileage step."""
        pass

    def click_submit(self) -> bool:
        """
        Minimal: click the Submit button on this page.
        Tries 'Submit' first, then 'Submit Complaint'. Returns True if clicked.
        """
        if click_element_by_text(self.driver, tag="button", text="Submit", timeout=6):
            print("[COMPLAINT] Submit clicked")
            return True
        if click_element_by_text(
            self.driver, tag="button", text="Submit Complaint", timeout=4
        ):
            print("[COMPLAINT] 'Submit Complaint' clicked")
            return True
        print("[COMPLAINT][WARN] Submit button not found")
        return False
