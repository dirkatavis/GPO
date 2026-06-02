"""Vehicle Details view (post-scan).

Locator strategy: stable `data-key` attributes on each row. React-Aria
generated ids are intentionally avoided. See
`/memories/repo/compass-go-locator-strategy.md`.

Confirmed data-key values:
    vinNo          -> VIN row
    mvaNo          -> MVA row
    makeModelDesc  -> Description row (Make/Model)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

DATA_KEY_VIN = "vinNo"
DATA_KEY_MVA = "mvaNo"
DATA_KEY_DESC = "makeModelDesc"


class VehicleDetailsPage:
    """Read-only view: scraped fields + expand/collapse + back navigation."""

    def __init__(self, page: "Page"):
        self._page = page

    def read(self, data_key: str) -> str:
        """Return the value cell text for the row with the given data-key.

        Returns an empty string if the row exists but the cell is empty.
        Caller (writer) is responsible for coercing to N/A.
        """
        locator = self._page.locator(f'tr[data-key="{data_key}"] td[role="gridcell"]')
        return locator.inner_text().strip()

    def expand_show_more(self) -> None:
        """Click Show More to reveal hidden rows (including VIN).

        Idempotent: if already expanded (Show Less visible), this is a no-op.
        Button has no stable id/data-attr; matched by accessible name.
        """
        show_less = self._page.get_by_role("button", name="Show Less", exact=True)
        if show_less.count() > 0 and show_less.first.is_visible():
            return
        self._page.get_by_role("button", name="Show More", exact=True).click()
        show_less.wait_for()

    def back(self) -> None:
        """Navigate back via the chevron-left button (class `back-button`)."""
        self._page.locator("button.back-button").click()
