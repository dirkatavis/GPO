# FILE: pages/complaint_items_tab.py
# PASTE THIS FULL FILE

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .base_page import BasePage
from .complaint import Complaint

try:
    from selenium.webdriver.common.by import By
except Exception:

    class _By:
        CSS_SELECTOR = "css selector"
        XPATH = "xpath"
        ID = "id"
        NAME = "name"

    By = _By()  # type: ignore


class ComplaintItemsTab(BasePage):
    """Represents the Complaints tab/dialog (0+ complaint items)."""

    # ---- Selector constants -------------------------------------------------
    class S:
        # Tab header (activate if needed)
        TAB_HEADER: Tuple[str, str] = (
            By.XPATH,
            "//span[normalize-space()='Complaints']",
        )

        # Add Complaint button
        ADD_COMPLAINT_BTN: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "button[data-testid='add-complaint'], button.fleet-operations-pwa__create-item-button__1gmnvu9",
        )

        # One complaint tile/card
        ITEM_TILE: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "div.fleet-operations-pwa__complaintItem__153vo4c, div[data-testid='complaint-tile']",
        )

        # Within a tile
        ITEM_ID: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "[data-field='id'], [data-testid='complaint-id'], .complaint-id",
        )
        ITEM_TYPE: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "div.fleet-operations-pwa__tileContent__153vo4c, [data-field='type'], .complaint-type",
        )
        ITEM_STATUS: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "[data-field='status'], [data-testid='complaint-status'], .complaint-status",
        )
        ITEM_CREATED_AT: Tuple[str, str] = (
            By.CSS_SELECTOR,
            "[data-field='createdAt'], [data-testid='complaint-created-at'], .complaint-created-at",
        )

    # ---- Public API (stubs) ------------------------------------------------
    def ensure_active(self) -> None:
        """Later: click TAB_HEADER if tab/dialog content isn’t visible."""
        pass

    def list_complaints(self) -> List[Complaint]:
        """Return all Complaint objects currently shown (stubbed)."""
        return []

    def click_add_complaint(self) -> None:
        """Click the 'Add Complaint' button (stub)."""
        pass

    # ---- Private helpers (shapes only) ------------------------------------
    def _extract_tile_fields(self, tile_el) -> Dict[str, Optional[str]]:
        """Shape for future DOM extraction."""
        return {"id": None, "type": None, "status": None, "created_at": None}

    def _to_complaint(self, raw: Dict[str, Optional[str]]) -> Complaint:
        """Map raw strings -> Complaint (no parsing yet)."""
        return Complaint(
            id=raw.get("id") or "",
            type=(raw.get("type") or "").strip(),
            status=(raw.get("status") or "").strip() or "Open",
            created_at=None,
        )
