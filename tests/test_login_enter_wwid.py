"""
Unit tests for enter_wwid() in playwright_prototype.login.

Covers the same-tab navigation case: Submit is clicked, the page navigates
within the same tab (no new page event), and the function must not attempt a
second click that would time out on the now-gone button.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_page_mock(submit_visible_after_navigate: bool = False):
    """Return a page mock that simulates same-tab Submit navigation.

    submit_visible_after_navigate=False  → Submit disappears after click
    submit_visible_after_navigate=True   → Submit stays (for second-click path)
    """
    page = MagicMock()
    page.url = "https://compassapp.example.com/app"
    page.wait_for_timeout = AsyncMock()

    # WWID input — always visible
    wwid_input = AsyncMock()
    wwid_input.wait_for = AsyncMock()
    wwid_input.fill = AsyncMock()

    # Submit button — wait_for fails if gone after navigate; click fails on second attempt if gone
    async def submit_wait_for(state=None, timeout=None):
        if not submit_visible_after_navigate:
            raise Exception("element not visible after navigation")

    submit_click_calls = 0

    async def submit_click(**kwargs):
        nonlocal submit_click_calls
        submit_click_calls += 1
        if submit_click_calls >= 2 and not submit_visible_after_navigate:
            raise Exception(
                'Locator.click: Timeout 10000ms exceeded.'
                ' waiting for get_by_role("button", name="Submit")'
            )

    submit_btn = AsyncMock()
    submit_btn.wait_for = AsyncMock(side_effect=submit_wait_for)
    submit_btn.click = AsyncMock(side_effect=submit_click)

    page.locator = MagicMock(return_value=wwid_input)
    page.get_by_role = MagicMock(return_value=submit_btn)

    # expect_page context manager — raises (no new tab opened)
    class _NoNewPage:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        @property
        def value(self):
            raise Exception("No new page")

    page.context = MagicMock()
    page.context.expect_page = MagicMock(return_value=_NoNewPage())

    return page, submit_btn


class TestEnterWwidSameTabNavigation:
    """enter_wwid must not raise when Submit navigates in the same tab."""

    def test_same_tab_navigation_does_not_raise(self):
        """When no new tab opens and Submit is gone after click, enter_wwid succeeds."""
        from playwright_prototype.login import enter_wwid

        page, submit_btn = _make_page_mock(submit_visible_after_navigate=False)

        # Should complete without raising RuntimeError
        result = asyncio.run(enter_wwid(page, "E96693"))
        assert result is page

    def test_same_tab_navigation_does_not_click_submit_twice(self):
        """When no new tab opens and Submit is gone, the second click is skipped."""
        from playwright_prototype.login import enter_wwid

        page, submit_btn = _make_page_mock(submit_visible_after_navigate=False)
        asyncio.run(enter_wwid(page, "E96693"))

        # click() is called once (inside expect_page block), not a second time
        assert submit_btn.click.call_count == 1

    def test_second_click_still_fires_when_submit_stays_visible(self):
        """When no new tab opens but Submit is still there, the fallback click runs."""
        from playwright_prototype.login import enter_wwid

        page, submit_btn = _make_page_mock(submit_visible_after_navigate=True)
        asyncio.run(enter_wwid(page, "E96693"))

        assert submit_btn.click.call_count == 2
