from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

from config.config_loader import get_config
from playwright_prototype.config import LOGIN_URL, SSO_EMAIL

log = logging.getLogger(__name__)


async def fill_sso_email(page: Page, username: str) -> None:
    log.info("[LOGIN] Entering SSO email: %s", username)
    try:
        await page.locator('input[name="loginfmt"]').fill(username, timeout=10_000)
        await page.locator("#idSIButton9").click(timeout=10_000)
    except Exception as exc:
        raise RuntimeError(f"[LOGIN] SSO email step failed: {exc}") from exc


async def fill_sso_password(page: Page, password: str) -> None:
    log.info("[LOGIN] Entering SSO password")
    try:
        await page.locator('input[name="passwd"]').fill(password, timeout=10_000)
        await page.locator("#idSIButton9").click(timeout=10_000)
        # Allow the Microsoft auth redirect to settle
        await page.wait_for_timeout(2_000)
    except Exception as exc:
        raise RuntimeError(f"[LOGIN] SSO password step failed: {exc}") from exc


async def dismiss_stay_signed_in(page: Page) -> None:
    """Click 'No' on the 'Stay signed in?' dialog — safe to skip if absent."""
    try:
        no_btn = page.locator("#idBtn_Back")
        await no_btn.wait_for(state="visible", timeout=3_000)
        await no_btn.click()
        log.info("[LOGIN] Dismissed 'Stay signed in?' dialog")
    except Exception:
        log.info("[LOGIN] 'Stay signed in?' dialog not shown — continuing")


async def select_sso_account(page: Page, sso_email: str) -> None:
    """Select an account from the Microsoft 'Pick an account' picker if it appears."""
    log.info("[LOGIN] Selecting SSO account: %s", sso_email)
    try:
        # Matches pages/MicrosoftSSOPage.py aria-label / data-testid identifiers
        sso_container = page.locator(
            '[aria-label*="Pick an account"], [data-testid="sso-page-identifier"]'
        )
        await sso_container.wait_for(state="visible", timeout=5_000)
        tile = page.locator('[data-testid="account-tile"]').filter(has_text=sso_email)
        await tile.click(timeout=10_000)
        log.info("[LOGIN] SSO account selected")
    except Exception as exc:
        raise RuntimeError(f"[LOGIN] SSO account selection failed: {exc}") from exc


async def click_compass_mobile_tile(page: Page) -> Page:
    """Click the 'Compass Mobile' app launcher; returns the new Page that opens in a new tab."""
    log.info("[LOGIN] Clicking Compass Mobile tile (current URL: %s)", page.url)
    try:
        compass_app_label = str(get_config("compass_app_label", "Compass Mobile"))
        tile = page.locator(
            f"//a[@role='button']//span[contains(normalize-space(.), '{compass_app_label}')]"
        )
        # Compass Mobile opens a new browser tab — capture it via expect_page
        async with page.context.expect_page() as new_page_info:
            await tile.click(timeout=20_000)
        new_page = await new_page_info.value
        await new_page.wait_for_load_state("domcontentloaded")
        log.info("[LOGIN] Switched to Compass Mobile tab")
        return new_page
    except Exception as exc:
        screenshot_path = Path(__file__).resolve().parent.parent / "playwright_debug.png"
        try:
            await page.screenshot(path=str(screenshot_path))
            log.info("[LOGIN] Screenshot saved to %s", screenshot_path)
        except Exception:
            pass
        raise RuntimeError(f"[LOGIN] Compass Mobile tile click failed: {exc}") from exc


async def enter_wwid(page: Page, login_id: str) -> None:
    """Type the WWID into the Compass Mobile entry screen and submit."""
    log.info("[LOGIN] Entering WWID: %s", login_id)
    try:
        # Hashed class selector — same one used in pages/login_page.py enter_wwid()
        wwid_input = page.locator('input[class*="fleet-operations-pwa__text-input__"]')
        await wwid_input.wait_for(state="visible", timeout=10_000)
        await wwid_input.fill(login_id)
        await page.get_by_role("button", name="Submit").click(timeout=10_000)
        log.info("[LOGIN] WWID submitted")
    except Exception as exc:
        raise RuntimeError(f"[LOGIN] WWID entry failed: {exc}") from exc


async def perform_full_login(
    page: Page,
    *,
    username: str,
    password: str,
    login_id: str,
    sso_email: str,
) -> Page:
    """Run the complete Compass login chain and return the page on the OpCode list.

    Returns the new Page because clicking Compass Mobile opens a new tab.
    Caller must use the returned Page; the original page object is no longer current.
    """
    log.info("[LOGIN] Starting full login flow")
    await page.goto(LOGIN_URL, wait_until="networkidle")
    log.info("[LOGIN] Landing URL: %s", page.url)

    # Check if login form is visible — mirrors Selenium ensure_logged_in() logic.
    # Don't infer auth state from intermediate redirect URLs; check the actual page.
    try:
        await page.locator('input[name="loginfmt"]').wait_for(state="visible", timeout=5_000)
        log.info("[LOGIN] Login form detected — filling credentials")
        await fill_sso_email(page, username)
        await fill_sso_password(page, password)
        await dismiss_stay_signed_in(page)
    except Exception:
        log.info("[LOGIN] No login form — already authenticated (URL: %s)", page.url)

    # SSO account picker is optional — appears on first login or after session drop
    try:
        sso_indicator = page.locator(
            '[aria-label*="Pick an account"], [data-testid="sso-page-identifier"]'
        )
        await sso_indicator.wait_for(state="visible", timeout=5_000)
        await select_sso_account(page, sso_email)
    except Exception:
        log.info("[LOGIN] No SSO account picker — continuing")

    compass_page = await click_compass_mobile_tile(page)
    await enter_wwid(compass_page, login_id)

    log.info("[LOGIN] Full login complete")
    return compass_page
