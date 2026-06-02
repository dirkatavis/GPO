"""Vehicle Details view (post-scan).

Locator strategy: stable `data-key` attributes on each row. React-Aria
generated ids are intentionally avoided. See
`/memories/repo/compass-go-locator-strategy.md`.

Confirmed data-key values:
    vinNo  -> VIN row
Pending (TODO — capture from DOM):
    ?      -> Description row (likely `desc` or `description`)
    ?      -> MVA row (likely `mva` or `mvaNo`)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

# Tentative — update when DOM snippets confirm the real keys.
DATA_KEY_VIN = "vinNo"
DATA_KEY_DESC = "desc"
DATA_KEY_MVA = "mva"


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

        TODO: confirm button selector from DOM snippet. Current fallback uses
        accessible name match. Idempotent — no-op when already expanded.
        """
        import re

        toggle = self._page.get_by_role("button", name=re.compile(r"Show More", re.IGNORECASE))
        if toggle.count() > 0 and toggle.first.is_visible():
            toggle.first.click()
            self._page.get_by_role("button", name=re.compile(r"Show Less", re.IGNORECASE)).wait_for()

    def back(self) -> None:
        """TODO: implement once back-arrow selector confirmed."""
        raise NotImplementedError("back(): pending back-arrow DOM snippet")
