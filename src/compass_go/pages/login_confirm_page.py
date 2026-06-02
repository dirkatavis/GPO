"""'Welcome back!' identity-confirm page.

TODO: confirm Continue / Switch User / Log out button selectors from DOM.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page


class LoginConfirmPage:
    def __init__(self, page: "Page"):
        self._page = page

    def is_displayed(self) -> bool:
        return self._page.get_by_role(
            "heading", name="Welcome back! Please confirm your identity:"
        ).is_visible()

    def continue_as_current_user(self) -> None:
        self._page.get_by_role("button", name="Continue").click()
