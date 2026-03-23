# FILE: pages/opcode_dialog.py
# PASTE THIS FULL FILE

from __future__ import annotations

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


class OpcodeDialog(BasePage):
    """Represents the Opcode selection dialog (â‰ˆ20 options, incl. PM Gas)."""

    # ---- Selector constants -------------------------------------------------
    class S:
        DIALOG: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "div.bp6-dialog[data-testid='opcode-dialog'], div.fleet-operations-pwa__opcodeDialog",
        )
        OPCODE_ITEM: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "div[data-testid='opcode-item'], div.fleet-operations-pwa__opcodeItem",
        )
        OPCODE_LABEL: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "span.opcode-label, div.fleet-operations-pwa__opcodeLabel",
        )
        CREATE_BTN: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "button[data-testid='opcode-create'], button.bp6-button.bp6-intent-primary",
        )

    # ---- Public API (stubs) ------------------------------------------------
    def ensure_open(self) -> None:
        """Later: wait until dialog S.DIALOG is visible."""
        pass

    def select_opcode(self, name: str) -> bool:
        # Try clicking an opcode item whose visible text (or child label) matches `name`.
        items = self.driver.find_elements(*self.S.OPCODE_ITEM)
        target = name.strip()
        for el in items:
            try:
                if el.text.strip() == target:
                    el.click()
                    return True
                label = el.find_element(*self.S.OPCODE_LABEL)
                if label.text.strip() == target:
                    label.click()
                    return True
            except Exception:
                continue
        # Fallback: click any matching label in the dialog.
        for lb in self.driver.find_elements(*self.S.OPCODE_LABEL):
            if lb.text.strip() == target:
                lb.click()
                return True
        return False

    def click_create(self) -> bool:
        try:
            self.driver.find_element(*self.S.CREATE_BTN).click()
            return True
        except Exception:
            return False

    def click_create_button(self) -> bool:
        return self.click_create()
