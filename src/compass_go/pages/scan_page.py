"""Scan Vehicle view — landing page with 'Begin Scanning' that reveals the
MVA/VIN input + Enter button.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from .vehicle_details_page import VehicleDetailsPage

CONTAINER = ".enter-mva-vin"
INPUT_ARIA_LABEL = "Or enter MVA/VIN"
BEGIN_SCANNING_NAME = "Begin Scanning"
SCAN_TAB_SELECTOR = 'button[role="tab"][data-key="scan"]'


class ScanPage:
    def __init__(self, page: "Page"):
        self._page = page

    def is_displayed(self) -> bool:
        # We're "on" Scan once either the landing button OR the MVA input is
        # visible — the page reuses the same URL across the two states.
        if self._page.get_by_role("button", name=BEGIN_SCANNING_NAME).is_visible():
            return True
        return self._page.get_by_label(INPUT_ARIA_LABEL).first.is_visible()

    def submit(self, mva: str) -> "VehicleDetailsPage":
        from .vehicle_details_page import VehicleDetailsPage

        # Reveal the MVA/VIN input if the landing button is still showing.
        begin = self._page.get_by_role("button", name=BEGIN_SCANNING_NAME)
        if begin.is_visible():
            begin.click()

        # Activate the Scan tab once it renders (the Begin Scanning click can
        # be slow — the app may take 30-60s to swap views). Skip if it's
        # already selected or absent.
        scan_tab = self._page.locator(SCAN_TAB_SELECTOR).first
        try:
            scan_tab.wait_for(state="visible", timeout=90_000)
            if scan_tab.get_attribute("aria-selected") != "true":
                scan_tab.click()
        except Exception:
            pass

        container = self._page.locator(CONTAINER)
        input_locator = self._page.get_by_label(INPUT_ARIA_LABEL).first
        if container.count():
            # Prefer the legacy scoped container when present (test fixture).
            input_locator = container.get_by_label(INPUT_ARIA_LABEL)
        input_locator.wait_for(timeout=90_000)
        input_locator.fill(mva)

        # Enter button sits next to the input. Use role+name; if multiple
        # Enter buttons exist, the one adjacent to the focused input wins.
        self._page.get_by_role("button", name="Enter", exact=True).first.click()
        self._page.get_by_role("heading", name="Vehicle Details").wait_for(timeout=90_000)
        return VehicleDetailsPage(self._page)
