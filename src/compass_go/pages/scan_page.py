"""Scan Vehicle view — MVA input + Enter button.

TODO: confirm textbox + Enter button selectors from DOM snippet. Current
implementation falls back to role-based locators which are typically stable
but may collide if the view adds more controls.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from .vehicle_details_page import VehicleDetailsPage


class ScanPage:
    def __init__(self, page: "Page"):
        self._page = page

    def is_displayed(self) -> bool:
        return self._page.get_by_role("textbox").first.is_visible()

    def submit(self, mva: str) -> "VehicleDetailsPage":
        from .vehicle_details_page import VehicleDetailsPage

        textbox = self._page.get_by_role("textbox").first
        textbox.fill(mva)
        self._page.get_by_role("button", name="Enter").click()
        self._page.get_by_role("heading", name="Vehicle Details").wait_for()
        return VehicleDetailsPage(self._page)
