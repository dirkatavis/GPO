"""
Unit tests for handle_complaint_dialog() — playwright_prototype/steps.py.

Covers the existing-complaint path: a glass complaint tile is already present
in the dialog, so the function clicks it, clicks Next, verifies the mileage
dialog appears, and returns without entering the create-new path.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_page_mock():
    """Return a page mock that simulates the existing-complaint dialog state."""
    page = MagicMock()
    page.wait_for_timeout = AsyncMock()
    page.url = "https://app.example.com/work-order"

    # Glass complaint tile — count > 0 signals existing complaint
    tile_first = MagicMock()
    tile_first.click = AsyncMock()

    complaint_filtered = MagicMock()
    complaint_filtered.count = AsyncMock(return_value=1)
    complaint_filtered.first = tile_first

    complaint_locator = MagicMock()
    complaint_locator.filter = MagicMock(return_value=complaint_filtered)

    # Mileage heading — first probe succeeds so mileage_appeared=True
    mileage_first = AsyncMock()
    mileage_first.wait_for = AsyncMock()

    mileage_heading = MagicMock()
    mileage_heading.first = mileage_first

    # Next button
    next_btn = AsyncMock()
    next_btn.click = AsyncMock()

    # Add New Complaint button — must NOT be clicked on the existing path
    add_new_btn_first = AsyncMock()
    add_new_btn_first.click = AsyncMock()
    add_new_locator = MagicMock()
    add_new_locator.first = add_new_btn_first

    def locator_side_effect(selector, **kwargs):
        if "complaintItem" in str(selector):
            return complaint_locator
        if "Add New Complaint" in str(selector) or "Create New Complaint" in str(selector):
            return add_new_locator
        return MagicMock()

    def get_by_role_side_effect(role, **kwargs):
        name = str(kwargs.get("name", ""))
        if role == "button" and "Next" in name:
            return next_btn
        if role == "heading":
            return mileage_heading
        return AsyncMock()

    page.locator = MagicMock(side_effect=locator_side_effect)
    page.get_by_role = MagicMock(side_effect=get_by_role_side_effect)
    page.get_by_text = MagicMock(return_value=MagicMock(first=AsyncMock()))

    return page, tile_first, next_btn, add_new_btn_first


class TestHandleComplaintDialogExistingPath:
    """Existing-complaint path: tile found → click → Next → mileage dialog."""

    def test_existing_tile_is_clicked(self):
        """The glass complaint tile is clicked when it is already present."""
        from playwright_prototype.steps import handle_complaint_dialog

        page, tile_first, next_btn, _ = _make_page_mock()
        asyncio.run(handle_complaint_dialog(page, "59002156", "WS", "Replace"))

        tile_first.click.assert_called_once()

    def test_next_button_clicked_after_tile(self):
        """Next is clicked to advance to the mileage dialog after selecting the tile."""
        from playwright_prototype.steps import handle_complaint_dialog

        page, tile_first, next_btn, _ = _make_page_mock()
        asyncio.run(handle_complaint_dialog(page, "59002156", "WS", "Replace"))

        next_btn.click.assert_called_once()

    def test_add_new_complaint_not_clicked(self):
        """Add New Complaint must not be triggered when an existing tile is found."""
        from playwright_prototype.steps import handle_complaint_dialog

        page, _, _, add_new_btn_first = _make_page_mock()
        asyncio.run(handle_complaint_dialog(page, "59002156", "WS", "Replace"))

        add_new_btn_first.click.assert_not_called()

    def test_does_not_raise(self):
        """Function completes without error when an existing glass complaint is present."""
        from playwright_prototype.steps import handle_complaint_dialog

        page, _, _, _ = _make_page_mock()
        asyncio.run(handle_complaint_dialog(page, "59002156", "WS", "Replace"))
