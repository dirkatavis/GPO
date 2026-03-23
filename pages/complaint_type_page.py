# FILE: pages/complaint_type_page.py
# PASTE THIS FULL FILE

from __future__ import annotations

from typing import Tuple

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

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


class ComplaintTypePage(BasePage):
    """Select a specific complaint type (e.g., PM) after Drivability."""

    # ---- Selector constants -------------------------------------------------
    class S:
        DIALOG: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "div.bp6-dialog[data-testid='complaint-type-page'], div.fleet-operations-pwa__complaintTypePage",
        )
        TYPE_ITEM: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "div[data-testid='complaint-type-item'], div.fleet-operations-pwa__complaintTypeItem",
        )
        TYPE_LABEL: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "span.complaint-type-label, div.fleet-operations-pwa__complaintTypeLabel",
        )
        NEXT_BTN: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "button[data-testid='complaint-type-next'], button.bp6-button.bp6-intent-primary",
        )

    def ensure_open(self) -> None:
        """Later: wait until page/dialog is visible (S.DIALOG)."""
        pass

    def select_type(self, name: str) -> None:
        """
        Stub: locate and click a complaint type by visible text.
        Example: select_type('PM')
        """
        pass

    def click_next(self) -> None:
        """Stub: advance to the Additional Information page."""
        pass

    def select_pm_tile(self, mva=None) -> bool:
        """Select the 'PM' tile (auto-forwards). Returns True if clicked."""
        try:
            # Exact structure from live DOM: button.damage-option-button -> span -> h1 'PM'
            loc = (
                By.XPATH,
                "//button[contains(@class,'damage-option-button')][.//h1[normalize-space()='PM']]",
            )
            btn = WebDriverWait(self.driver, 6).until(EC.element_to_be_clickable(loc))
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", btn
            )
            btn.click()
            log.info(f"[COMPLAINT] {mva or ''} - PM tile clicked (auto-forward)")
            return True
        except Exception:
            log.warning(
                "[COMPLAINT][WARN] {mva or ''} - PM tile not found/clickable ({e})"
            )
            return False
