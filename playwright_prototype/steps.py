from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from config.config_loader import get_config

if TYPE_CHECKING:
    from playwright.async_api import Page

log = logging.getLogger(__name__)
DATA_ENTRY_SUBMIT_DELAY_MS = 2000
BUTTON_PUSH_DELAY_MS = 2000

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _map_damage_type(location: str, action: str) -> str:
    """Map CSV location + action to the Compass glass damage type button label.

    Business rule: REPAIR is only valid for windshields; all other areas are
    always REPLACEMENT regardless of the action column value.
    """
    loc = (location or "").strip().upper()
    act = (action or "REPLACE").strip().upper()
    if loc in ("WS", "WINDSHIELD", "FRONT"):
        return "Windshield Chip" if act in ("REPAIR", "CHIP") else "Windshield Crack"
    return "Side/Rear Window Damage"


async def _enter_mva(page: Page, mva: str) -> None:
    """Type an MVA into the Compass search field using a defensive locator chain."""
    locators = [
        'input.bp6-input[placeholder*="Enter MVA"]',
        'input[type="text"][placeholder*="MVA"]',
        'div[role="tabpanel"][aria-hidden="false"] input[type="text"]',
    ]
    for selector in locators:
        try:
            field = page.locator(selector).first
            await field.wait_for(state="visible", timeout=5_000)

            # Some Compass states keep a prior MVA cached in the input. Use
            # a strict clear/type path and verify the final value.
            await field.click(timeout=5_000)
            await field.press("Control+a")
            await field.press("Backspace")
            await field.fill(mva)

            current_value = (await field.input_value()).strip()
            if current_value != mva:
                await field.press("Control+a")
                await field.type(mva, delay=30)
                current_value = (await field.input_value()).strip()

            if current_value != mva:
                raise RuntimeError(
                    f"[STEPS] MVA field value mismatch (expected={mva}, actual={current_value})"
                )

            # Trigger downstream lookup in case the app only reacts to key events.
            await page.wait_for_timeout(DATA_ENTRY_SUBMIT_DELAY_MS)
            await field.press("Enter")
            return
        except Exception:
            continue
    raise RuntimeError(f"[STEPS] MVA input field not found for MVA {mva}")


# ─── Warmup & Navigation ─────────────────────────────────────────────────────

async def warmup_compass(page: Page) -> None:
    """Enter a dummy MVA to fully initialize the Compass app before real MVAs.

    Mirrors mva_navigation.warmup_compass() — primes the app state so the
    first real MVA loads reliably.
    """
    dummy_mva = str(get_config("warmup_mva", "50227203"))
    log.info("[STEPS] Warming up Compass with dummy MVA %s", dummy_mva)
    try:
        await _enter_mva(page, dummy_mva)
        await page.locator("button:not([disabled])").filter(
            has_text="Add Work Item"
        ).wait_for(state="visible", timeout=30_000)
        log.info("[STEPS] Compass warm-up complete")
    except Exception:
        log.warning("[STEPS] Warm-up: 'Add Work Item' not confirmed within timeout — proceeding anyway")


async def navigate_to_mva(page: Page, mva: str) -> None:
    """Enter an MVA and wait for the vehicle page to fully load.

    Waits for 'Add Work Item' to be enabled (not just visible) — the button
    appears immediately in a disabled/loading state while vehicle data fetches,
    so checking for enabled confirms the page is truly ready.
    """
    log.info("[STEPS] %s — navigating", mva)
    try:
        vehicle_url_template = str(get_config("compass_vehicle_url_template", "")).strip()
        if vehicle_url_template:
            try:
                expected_vehicle_url = vehicle_url_template.format(mva=mva)
                if page.url != expected_vehicle_url:
                    log.info("[STEPS] %s — opening vehicle URL directly", mva)
                    await page.goto(expected_vehicle_url, wait_until="domcontentloaded")
                else:
                    log.info("[STEPS] %s — already on vehicle URL", mva)
            except Exception as exc:
                log.warning(
                    "[STEPS] %s — invalid compass_vehicle_url_template, falling back to MVA entry (%s)",
                    mva,
                    exc,
                )

        await _enter_mva(page, mva)
        await page.locator("button:not([disabled])").filter(
            has_text="Add Work Item"
        ).wait_for(state="visible", timeout=30_000)
        log.info("[STEPS] %s — vehicle page loaded", mva)
    except Exception as exc:
        raise RuntimeError(f"[STEPS] navigate_to_mva failed for {mva}: {exc}") from exc


# ─── Work Item Flow ───────────────────────────────────────────────────────────

async def click_add_work_item(page: Page, mva: str) -> None:
    """Click the 'Add Work Item' button to open the complaint/work-item dialog."""
    log.info("[STEPS] %s — clicking 'Add Work Item'", mva)
    try:
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await page.get_by_role("button", name="Add Work Item").click(timeout=10_000)
        log.info("[STEPS] %s — 'Add Work Item' clicked", mva)
    except Exception as exc:
        raise RuntimeError(f"[STEPS] click_add_work_item failed for {mva}: {exc}") from exc


async def _click_submit_complaint(page: Page, mva: str) -> None:
    """Click Submit Complaint with fallback click strategies for complex UI events."""
    submit_button = page.get_by_role(
        "button", name=re.compile(r"Submit Complaint|Submit", re.I)
    ).first
    await submit_button.wait_for(state="visible", timeout=20_000)

    try:
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await submit_button.click(timeout=8_000)
        return
    except Exception:
        pass

    try:
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await submit_button.click(timeout=8_000, force=True)
        return
    except Exception:
        pass

    handle = await submit_button.element_handle()
    if handle is None:
        raise RuntimeError(f"[STEPS] {mva} — submit button handle unavailable")
    await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
    await page.evaluate("(el) => el.click()", handle)


async def _wait_for_post_submit_progress(page: Page, previous_url: str) -> bool:
    """Return True when submit progresses to a new state (URL change or mileage UI)."""
    try:
        await page.wait_for_function(
            "prev => window.location.href !== prev",
            arg=previous_url,
            timeout=10_000,
        )
        return True
    except Exception:
        pass

    mileage_locators = [
        page.get_by_role("heading", name=re.compile(r"Mileage", re.I)),
        page.get_by_text(re.compile(r"\bMileage\b", re.I)),
        page.locator('input[placeholder*="Mileage" i], input[aria-label*="Mileage" i]'),
    ]
    for locator in mileage_locators:
        try:
            await locator.first.wait_for(state="visible", timeout=4_000)
            return True
        except Exception:
            continue
    return False


async def handle_complaint_dialog(page: Page, mva: str, location: str, action: str, step_delay_ms: int = 0) -> None:
    """Associate an existing glass complaint or create a new one.

    Existing path: find glass complaint tile → click → Next (advances to mileage).
    New path: Add New Complaint → Drivability → Glass Damage → damage type → Submit.
    Both paths leave the page on the mileage dialog for complete_mileage_dialog().
    """
    log.info("[STEPS] %s — handling complaint dialog (location=%s action=%s)", mva, location, action)

    async def delay():
        if step_delay_ms:
            await page.wait_for_timeout(step_delay_ms)

    try:
        await page.wait_for_timeout(2_000)

        glass_tile = page.locator(
            '[class*="fleet-operations-pwa__complaintItem__"]'
        ).filter(has_text=re.compile(r"glass|windshield|crack|chip|window", re.I))

        if await glass_tile.count() > 0:
            log.info("[STEPS] %s — found existing glass complaint, associating", mva)
            await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
            await glass_tile.first.click(timeout=5_000);  await delay()
            await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
            await page.get_by_role("button", name="Next").click(timeout=10_000)
            return

        # No existing complaint — create new
        log.info("[STEPS] %s — no existing glass complaint, creating new", mva)
        add_btn = page.locator(
            "//button[.//p[contains(text(),'Add New Complaint')] or .//p[contains(text(),'Create New Complaint')]]"
            " | //button[normalize-space()='Add New Complaint']"
            " | //button[normalize-space()='Create New Complaint']"
        ).first
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await add_btn.click(timeout=10_000);  await delay()

        drivability = str(get_config("default_drivability", "Yes"))
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await page.get_by_role("button", name=drivability).click(timeout=10_000)
        log.info("[STEPS] %s — drivability: %s", mva, drivability);  await delay()

        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await page.get_by_role("button", name="Glass Damage").click(timeout=10_000);  await delay()

        damage_label = _map_damage_type(location, action)
        log.info("[STEPS] %s — selecting damage type: %s", mva, damage_label)
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await page.locator(f'//button[.//h1[text()="{damage_label}"]]').click(timeout=10_000);  await delay()

        pre_submit_url = page.url
        await _click_submit_complaint(page, mva)
        log.info("[STEPS] %s — new glass complaint submitted", mva)

        if await _wait_for_post_submit_progress(page, pre_submit_url):
            return

        log.warning(
            "[STEPS] %s — submit did not show mileage/url transition; attempting complaint association fallback",
            mva,
        )

        # After Submit, the app may return to the complaint list rather than
        # auto-advancing to the mileage dialog.  If so, select the new complaint
        # and click Next exactly as in the existing-complaint path.
        await page.wait_for_timeout(2_000)
        glass_tile_post = page.locator(
            '[class*="fleet-operations-pwa__complaintItem__"]'
        ).filter(has_text=re.compile(r"glass|windshield|crack|chip|window", re.I))
        if await glass_tile_post.count() > 0:
            log.info("[STEPS] %s — post-submit: complaint list shown, associating new complaint", mva)
            await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
            await glass_tile_post.first.click(timeout=5_000)
            await delay()
            await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
            await page.get_by_role("button", name="Next").click(timeout=10_000)

        if not await _wait_for_post_submit_progress(page, pre_submit_url):
            raise RuntimeError(
                "[STEPS] "
                f"{mva} — submit completed without mileage/url transition; backend may have rejected write"
            )

    except Exception as exc:
        raise RuntimeError(f"[STEPS] handle_complaint_dialog failed for {mva}: {exc}") from exc


async def complete_mileage_dialog(page: Page, mva: str) -> None:
    """Advance past the mileage dialog by clicking Next.

    Mirrors mileage_flows.complete_mileage_dialog() — the mileage value is
    typically pre-populated from the vehicle record.
    """
    log.info("[STEPS] %s — advancing past mileage dialog", mva)
    try:
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await page.get_by_role("button", name="Next").click(timeout=10_000)
        log.info("[STEPS] %s — mileage dialog advanced", mva)
    except Exception as exc:
        raise RuntimeError(f"[STEPS] complete_mileage_dialog failed for {mva}: {exc}") from exc


async def select_glass_opcode(page: Page) -> None:
    """Wait for the OpCode list to render then click 'Glass Repair/Replace'.

    Waits for any opCodeText element first (list load), then finds and scrolls
    to the target tile — mirrors opcode_flows.select_opcode().
    """
    log.info("[STEPS] Selecting 'Glass Repair/Replace' OpCode")
    try:
        await page.locator('[class*="opCodeText"]').first.wait_for(
            state="visible", timeout=15_000
        )
        target = page.get_by_text("Glass Repair/Replace", exact=True)
        await target.scroll_into_view_if_needed()
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await target.click(timeout=10_000)
        log.info("[STEPS] OpCode selected")
    except Exception as exc:
        raise RuntimeError(f"[STEPS] select_glass_opcode failed: {exc}") from exc


async def create_work_item(page: Page) -> None:
    """Click the 'Create Work Item' button.

    Tries an exact text match first (matches finalize_flow.py XPath). Falls
    back to the enabled-button-in-container heuristic if the button has no
    visible label (as seen in earlier Compass versions).
    """
    log.info("[STEPS] Clicking 'Create Work Item' button")
    try:
        button = page.get_by_role("button", name="Create Work Item")
        if await button.count() == 0:
            log.info("[STEPS] Exact name not found — using container fallback")
            button = page.locator(
                "[class*='fleet-operations-pwa__generalContainer__'] "
                "button:not([class*='bp6-disabled'])"
            ).first
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await button.click(timeout=10_000)
        log.info("[STEPS] 'Create Work Item' clicked")
    except Exception as exc:
        raise RuntimeError(f"[STEPS] create_work_item failed: {exc}") from exc


async def confirm_completion(page: Page) -> None:
    """Click the final 'Done' button on the completion dialog."""
    log.info("[STEPS] Clicking 'Done' button")
    try:
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await page.get_by_role("button", name="Done").click(timeout=10_000)
        log.info("[STEPS] 'Done' clicked — workflow complete")
    except Exception as exc:
        raise RuntimeError(f"[STEPS] confirm_completion failed: {exc}") from exc
