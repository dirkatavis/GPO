from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page

from playwright_prototype.config import LOGIN_URL, SSO_EMAIL, STORAGE_STATE_PATH
from playwright_prototype.login import (
    click_compass_mobile_tile,
    enter_wwid,
    perform_full_login,
    select_sso_account,
)

log = logging.getLogger(__name__)


def _credentials() -> tuple[str, str, str, str]:
    """Read Compass login credentials — env vars take priority, config file as fallback."""
    from config.config_loader import get_config
    username = os.getenv("GLASS_LOGIN_USERNAME") or get_config("username")
    password = os.getenv("GLASS_LOGIN_PASSWORD") or get_config("password")
    login_id = os.getenv("GLASS_LOGIN_ID") or get_config("login_id")
    return username, password, login_id, SSO_EMAIL


async def _is_on_login_page(page: Page) -> bool:
    """True if the Microsoft SSO email form is visible (session expired or fresh start)."""
    try:
        await page.locator('input[name="loginfmt"]').wait_for(state="visible", timeout=3_000)
        return True
    except Exception:
        return False


async def _is_on_sso_picker(page: Page) -> bool:
    """True if the 'Pick an account' Microsoft SSO dialog is showing."""
    try:
        await page.locator(
            '[aria-label*="Pick an account"], [data-testid="sso-page-identifier"]'
        ).wait_for(state="visible", timeout=3_000)
        return True
    except Exception:
        return False


async def _is_on_compass_mobile_picker(page: Page) -> bool:
    """True if the Foundry workspace app tile for Compass Mobile is visible."""
    from config.config_loader import get_config
    try:
        label = str(get_config("compass_app_label", "Compass Mobile"))
        await page.locator(
            f"//a[@role='button']//span[contains(normalize-space(.), '{label}')]"
        ).wait_for(state="visible", timeout=3_000)
        return True
    except Exception:
        return False


async def _is_on_wwid_screen(page: Page) -> bool:
    """True if the Compass Mobile WWID entry input is visible."""
    try:
        await page.locator(
            'input[class*="fleet-operations-pwa__text-input__"]'
        ).wait_for(state="visible", timeout=3_000)
        return True
    except Exception:
        return False


_WEBDRIVER_MASK = "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"


async def _new_context(browser: Browser, *, no_viewport: bool = False, **kwargs) -> "BrowserContext":
    """Create a browser context with automation-detection masking applied."""
    context = await browser.new_context(permissions=[], no_viewport=no_viewport, **kwargs)
    await context.add_init_script(_WEBDRIVER_MASK)
    return context


async def _do_fresh_login(browser: Browser, *, no_viewport: bool = False) -> tuple[BrowserContext, Page]:
    """Create a new context and run a full login from scratch."""
    context = await _new_context(browser, no_viewport=no_viewport)
    page = await context.new_page()
    username, password, login_id, sso_email = _credentials()
    page = await perform_full_login(
        page,
        username=username,
        password=password,
        login_id=login_id,
        sso_email=sso_email,
    )
    return context, page


async def ensure_authenticated_context(browser: Browser, *, no_viewport: bool = False) -> tuple[BrowserContext, Page]:
    """Return (context, page) ready for select_glass_opcode().

    Strategy:
      1. If storage_state.json exists, restore it and navigate to the login URL.
      2. Detect where the restore landed and handle each partial-auth case.
      3. If session is fully expired, fall back to a complete fresh login.
      4. Always re-save state after a successful auth so rolling cookies stay fresh.
    """
    if STORAGE_STATE_PATH.exists():
        log.info("[SESSION] Restoring session from %s", STORAGE_STATE_PATH)
        context = await _new_context(browser, no_viewport=no_viewport, storage_state=str(STORAGE_STATE_PATH))
        page = await context.new_page()
        await page.goto(LOGIN_URL, wait_until="domcontentloaded")
        username, password, login_id, sso_email = _credentials()

        if await _is_on_login_page(page):
            log.info("[SESSION] Session expired — performing full login")
            await context.close()
            context, page = await _do_fresh_login(browser, no_viewport=no_viewport)

        elif await _is_on_sso_picker(page):
            log.info("[SESSION] SSO picker detected — selecting account")
            await select_sso_account(page, sso_email)
            page = await click_compass_mobile_tile(page)
            await enter_wwid(page, login_id)

        elif await _is_on_compass_mobile_picker(page):
            log.info("[SESSION] Compass Mobile picker detected — clicking tile")
            page = await click_compass_mobile_tile(page)
            await enter_wwid(page, login_id)

        elif await _is_on_wwid_screen(page):
            log.info("[SESSION] WWID screen detected — re-entering WWID")
            await enter_wwid(page, login_id)

        else:
            log.info("[SESSION] Session restored — already on OpCode list")

    else:
        log.info("[SESSION] No saved session — performing full login")
        context, page = await _do_fresh_login(browser, no_viewport=no_viewport)

    log.info("[SESSION] Saving session state to %s", STORAGE_STATE_PATH)
    await context.storage_state(path=str(STORAGE_STATE_PATH))

    return context, page
