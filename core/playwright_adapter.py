"""
Playwright adapter implementing a Selenium-compatible WebDriver interface.

Wraps a Playwright Page so that existing flows/pages written for Selenium
can run with a Playwright-backed browser without code changes.
"""
from __future__ import annotations

import logging
from typing import List, Optional

log = logging.getLogger("mc.automation")


# ─── By constants (mirrors selenium.webdriver.common.by.By) ──────────────────

class By:
    """Selector strategy constants matching selenium.webdriver.common.by.By."""
    ID = "id"
    XPATH = "xpath"
    CSS_SELECTOR = "css selector"
    CLASS_NAME = "class name"
    TAG_NAME = "tag name"
    NAME = "name"
    LINK_TEXT = "link text"
    PARTIAL_LINK_TEXT = "partial link text"


def _to_selector(by: str, value: str) -> str:
    """Convert a Selenium By/value pair to a Playwright selector string."""
    if by == By.XPATH:
        return f"xpath={value}"
    elif by == By.CSS_SELECTOR:
        return value
    elif by == By.ID:
        return f"#{value}"
    elif by == By.CLASS_NAME:
        return f".{value}"
    elif by == By.TAG_NAME:
        return value
    elif by == By.NAME:
        return f"[name='{value}']"
    elif by == By.LINK_TEXT:
        return f"text='{value}'"
    elif by == By.PARTIAL_LINK_TEXT:
        return f"text={value}"
    else:
        return value


# ─── Element wrapper ──────────────────────────────────────────────────────────

class PlaywrightElement:
    """
    Wraps a Playwright Locator to expose a Selenium WebElement-compatible
    interface: .click(), .send_keys(), .text, .get_attribute(), .is_displayed(),
    .is_enabled(), .clear(), .find_element(), .find_elements().
    """

    def __init__(self, locator) -> None:
        self._locator = locator

    # ── Actions ───────────────────────────────────────────────────────────────

    def click(self) -> None:
        self._locator.click()

    def send_keys(self, *values: str) -> None:
        """Fill the element.  Joins multiple values like Selenium does."""
        self._locator.fill("".join(str(v) for v in values))

    def clear(self) -> None:
        self._locator.clear()

    def submit(self) -> None:
        self._locator.evaluate("el => el.form && el.form.submit()")

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def text(self) -> str:
        return self._locator.inner_text()

    def get_attribute(self, name: str) -> Optional[str]:
        return self._locator.get_attribute(name)

    def is_displayed(self) -> bool:
        return self._locator.is_visible()

    def is_enabled(self) -> bool:
        return self._locator.is_enabled()

    def value_of_css_property(self, property_name: str) -> str:
        return self._locator.evaluate(
            f"el => window.getComputedStyle(el).getPropertyValue('{property_name}')"
        )

    # ── Child element location ─────────────────────────────────────────────────

    def find_element(self, by: str, value: str) -> "PlaywrightElement":
        selector = _to_selector(by, value)
        return PlaywrightElement(self._locator.locator(selector).first)

    def find_elements(self, by: str, value: str) -> List["PlaywrightElement"]:
        selector = _to_selector(by, value)
        return [PlaywrightElement(loc) for loc in self._locator.locator(selector).all()]

    # ── execute_script support (for driver.execute_script(..., element)) ───────

    def evaluate(self, script: str) -> object:
        """Run JavaScript with this element as the implicit `el` argument."""
        return self._locator.evaluate(f"el => {{ {script} }}")

    @property
    def _handle(self):
        """Return the underlying Playwright Locator (for advanced use)."""
        return self._locator


# ─── Driver wrapper ───────────────────────────────────────────────────────────

class PlaywrightUiDriver:
    """
    Selenium WebDriver-compatible interface backed by a Playwright Page.

    Allows existing flow and page code written for Selenium to run with a
    Playwright browser context with no changes to the calling code.

    Supported surface:
        Navigation : get(), current_url, title, page_source, back(), forward(), refresh()
        Elements   : find_element(), find_elements() — returns PlaywrightElement
        Timing     : implicitly_wait(), set_page_load_timeout()
        JS         : execute_script()
    """

    def __init__(self, page) -> None:
        self.page = page
        self._implicit_wait_ms = 30_000  # 30 s default (matches Selenium default 30 s)
        self.page.set_default_timeout(self._implicit_wait_ms)

    # ── Navigation ────────────────────────────────────────────────────────────

    def get(self, url: str) -> None:
        self.page.goto(url, wait_until="domcontentloaded")

    @property
    def current_url(self) -> str:
        return self.page.url

    @property
    def title(self) -> str:
        return self.page.title()

    @property
    def page_source(self) -> str:
        return self.page.content()

    def back(self) -> None:
        self.page.go_back()

    def forward(self) -> None:
        self.page.go_forward()

    def refresh(self) -> None:
        self.page.reload()

    def close(self) -> None:
        self.page.close()

    # ── Timing ────────────────────────────────────────────────────────────────

    def implicitly_wait(self, seconds: float) -> None:
        self._implicit_wait_ms = int(seconds * 1000)
        self.page.set_default_timeout(self._implicit_wait_ms)

    def set_page_load_timeout(self, seconds: float) -> None:
        self.page.set_default_navigation_timeout(int(seconds * 1000))

    # ── Element location ──────────────────────────────────────────────────────

    def find_element(self, by: str, value: str) -> PlaywrightElement:
        """
        Return the first matching element, waiting up to the implicit-wait timeout.
        Raises selenium.common.exceptions.NoSuchElementException if not found.
        """
        selector = _to_selector(by, value)
        try:
            loc = self.page.locator(selector).first
            loc.wait_for(state="attached", timeout=self._implicit_wait_ms)
            return PlaywrightElement(loc)
        except Exception as exc:
            # Re-raise as Selenium's NoSuchElementException so callers that
            # catch it (e.g. WebDriverWait) continue to work unchanged.
            try:
                from selenium.common.exceptions import NoSuchElementException
                raise NoSuchElementException(
                    f"No element found for {by}={value!r}"
                ) from exc
            except ImportError:
                raise RuntimeError(
                    f"No element found for {by}={value!r}"
                ) from exc

    def find_elements(self, by: str, value: str) -> List[PlaywrightElement]:
        """Return all matching elements; returns an empty list if none found."""
        selector = _to_selector(by, value)
        try:
            return [PlaywrightElement(loc) for loc in self.page.locator(selector).all()]
        except Exception:
            return []

    # ── JavaScript execution ──────────────────────────────────────────────────

    def execute_script(self, script: str, *args) -> object:
        """
        Execute JavaScript in the page context.

        Handles two common Selenium calling patterns:
          1. ``driver.execute_script("return document.readyState")``
          2. ``driver.execute_script("arguments[0].scrollIntoView(...);", element)``

        For pattern 2, if the first argument is a PlaywrightElement the script
        runs via Locator.evaluate() so the element handle is available.
        """
        js = script.strip()

        # Strip leading "return " — Playwright evaluate returns the last value.
        if js.lower().startswith("return "):
            js = js[7:]

        if not args:
            return self.page.evaluate(js)

        # If the first arg is a wrapped element, run via the locator so that
        # Playwright can resolve the element handle natively.
        first = args[0]
        if isinstance(first, PlaywrightElement):
            # Rewrite "arguments[0].<member>" → "el.<member>" for common patterns.
            import re
            el_script = re.sub(r"\barguments\[0\]", "el", js)
            return first._locator.evaluate(f"el => {{ {el_script} }}")

        # Generic: wrap in an IIFE that exposes args as an array.
        return self.page.evaluate(
            "(args) => { "
            "var arguments = args; "
            f"{js} "
            "}",
            list(args),
        )

    def execute_async_script(self, script: str, *args) -> object:
        return self.page.evaluate_handle(script, *args)
