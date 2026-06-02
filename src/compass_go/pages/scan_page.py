"""Scan Vehicle view — MVA input + Enter button.

Scoped to the `.enter-mva-vin` container so the locators won't collide with
other inputs that may appear elsewhere on the page.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from .vehicle_details_page import VehicleDetailsPage

CONTAINER = ".enter-mva-vin"
INPUT_ARIA_LABEL = "Or enter MVA/VIN"


class ScanPage:
    def __init__(self, page: "Page"):
        self._page = page

    def is_displayed(self) -> bool:
        return self._page.locator(CONTAINER).is_visible()

    def submit(self, mva: str) -> "VehicleDetailsPage":
        from .vehicle_details_page import VehicleDetailsPage

        container = self._page.locator(CONTAINER)
        container.get_by_label(INPUT_ARIA_LABEL).fill(mva)
        container.get_by_role("button", name="Enter", exact=True).click()
        self._page.get_by_role("heading", name="Vehicle Details").wait_for()
        return VehicleDetailsPage(self._page)
