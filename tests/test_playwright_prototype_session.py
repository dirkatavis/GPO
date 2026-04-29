"""
Unit tests for playwright_prototype.session — storage_state file detection.

Verifies that ensure_authenticated_context() takes the "restore" path when
storage_state.json exists and the "fresh login" path when it does not.

Uses AsyncMock to avoid any real browser or network activity.
No Playwright installation required to run these tests.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_browser_mock(context_mock):
    """Return a mock Browser whose new_context() always yields context_mock."""
    browser = MagicMock()
    browser.new_context = AsyncMock(return_value=context_mock)
    return browser


def _make_context_and_page_mocks(url_fragment: str = "/workspace/"):
    """Return (context, page) mocks that simulate landing on a given URL after goto()."""
    page = AsyncMock()
    # Simulate all page.locator(...).wait_for() calls timing out (i.e. nothing is visible)
    # so _is_on_login_page etc. all return False → "session restored" branch is taken.
    locator_mock = AsyncMock()
    locator_mock.wait_for = AsyncMock(side_effect=Exception("not visible"))
    locator_mock.first = locator_mock
    page.locator = MagicMock(return_value=locator_mock)
    page.goto = AsyncMock()
    page.url = f"https://example.com{url_fragment}"

    context = AsyncMock()
    context.new_page = AsyncMock(return_value=page)
    context.storage_state = AsyncMock()
    context.close = AsyncMock()
    return context, page


class TestStorageStateDetection:
    """Confirm which code path is entered based on storage_state.json presence."""

    def test_existing_storage_state_restores_context(self, tmp_path, monkeypatch):
        """When storage_state.json exists, new_context is called WITH storage_state arg."""
        state_file = tmp_path / "storage_state.json"
        state_file.write_text("{}", encoding="utf-8")

        context, page = _make_context_and_page_mocks("/workspace/")
        browser = _make_browser_mock(context)

        monkeypatch.setattr("playwright_prototype.session.STORAGE_STATE_PATH", state_file)
        monkeypatch.setenv("GLASS_LOGIN_USERNAME", "user@example.com")
        monkeypatch.setenv("GLASS_LOGIN_PASSWORD", "secret")
        monkeypatch.setenv("GLASS_LOGIN_ID", "E12345")

        async def run():
            from playwright_prototype.session import ensure_authenticated_context
            return await ensure_authenticated_context(browser)

        asyncio.run(run())
        call_kwargs = browser.new_context.call_args_list[0].kwargs
        assert call_kwargs.get("storage_state") == str(state_file)

    def test_missing_storage_state_triggers_fresh_login(self, tmp_path, monkeypatch):
        """When storage_state.json is absent, new_context is called with NO storage_state arg."""
        state_file = tmp_path / "storage_state.json"
        # Do NOT create the file

        context, page = _make_context_and_page_mocks("/workspace/")
        browser = _make_browser_mock(context)

        # perform_full_login returns a page mock; patch it so we don't hit real network
        fresh_page = AsyncMock()
        fresh_page.url = "https://example.com/workspace/"
        locator_mock = AsyncMock()
        locator_mock.wait_for = AsyncMock(side_effect=Exception("not visible"))
        locator_mock.first = locator_mock
        fresh_page.locator = MagicMock(return_value=locator_mock)

        monkeypatch.setattr("playwright_prototype.session.STORAGE_STATE_PATH", state_file)
        monkeypatch.setattr(
            "playwright_prototype.session.perform_full_login",
            AsyncMock(return_value=fresh_page),
        )
        monkeypatch.setenv("GLASS_LOGIN_USERNAME", "user@example.com")
        monkeypatch.setenv("GLASS_LOGIN_PASSWORD", "secret")
        monkeypatch.setenv("GLASS_LOGIN_ID", "E12345")

        async def run():
            from playwright_prototype.session import ensure_authenticated_context
            return await ensure_authenticated_context(browser)

        asyncio.run(run())

        # new_context must have been called WITHOUT a storage_state keyword argument
        call_kwargs = browser.new_context.call_args_list[0].kwargs
        assert "storage_state" not in call_kwargs
