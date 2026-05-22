from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from config.config_loader import get_config

_GLASS_PATTERN = re.compile(r"glass|windshield|crack|chip|window", re.I)
_PM_PATTERN = re.compile(r"PM", re.I)

COMPLAINT_TYPE_PATTERNS: dict[str, re.Pattern] = {
    "Glass": _GLASS_PATTERN,
    "PM":    _PM_PATTERN,
}

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
            log.info("[STEPS] %s — vehicle URL template configured: %s", mva, vehicle_url_template)
            try:
                expected_vehicle_url = vehicle_url_template.format(mva=mva)
                log.info("[STEPS] %s — resolved vehicle URL: %s", mva, expected_vehicle_url)
                if page.url != expected_vehicle_url:
                    log.info("[STEPS] %s — opening vehicle URL directly", mva)
                    await page.goto(expected_vehicle_url, wait_until="domcontentloaded")
                else:
                    log.info("[STEPS] %s — already on vehicle URL", mva)
            except Exception as exc:
                raise RuntimeError(
                    f"[STEPS] {mva} — invalid compass_vehicle_url_template: {exc}"
                ) from exc
        else:
            log.info(
                "[STEPS] %s — no compass_vehicle_url_template configured; using MVA entry on current page: %s",
                mva,
                page.url,
            )

        await _enter_mva(page, mva)
        await page.locator("button:not([disabled])").filter(
            has_text="Add Work Item"
        ).wait_for(state="visible", timeout=30_000)
        log.info("[STEPS] %s — vehicle page loaded", mva)
    except Exception as exc:
        raise RuntimeError(f"[STEPS] navigate_to_mva failed for {mva}: {exc}") from exc


# ─── Work Item Flow ───────────────────────────────────────────────────────────

class ExistingWorkItemError(Exception):
    """Raised when an open work item of the requested type already exists for an MVA."""


async def check_existing_work_item(page: Page, mva: str, type: str) -> None:
    """Raise ExistingWorkItemError if an open work item of the given type already exists.

    Uses COMPLAINT_TYPE_PATTERNS[type] to match tiles. Inspects work items on the
    vehicle page — aborts for this MVA if a matching open tile is found.
    """
    pattern = COMPLAINT_TYPE_PATTERNS.get(type, _GLASS_PATTERN)
    log.info("[STEPS] %s — checking for existing open %s work item", mva, type)
    try:
        container = page.locator('[class*="fleet-operations-pwa__scan-record__"]').first
        try:
            await container.wait_for(state="visible", timeout=8_000)
        except Exception:
            log.info("[STEPS] %s — no work items container found, safe to proceed", mva)
            return

        open_item = page.locator(
            '[class*="fleet-operations-pwa__scan-record__"]'
        ).filter(has_text=pattern).filter(has_text=re.compile(r"open", re.I))
        count = await open_item.count()
        if count > 0:
            tile_text = await open_item.first.inner_text()
            raise ExistingWorkItemError(
                f"{mva} — open {type} work item already exists: {tile_text.strip()!r}"
            )
        log.info("[STEPS] %s — no open %s work item found, safe to proceed", mva, type)
    except ExistingWorkItemError:
        raise
    except Exception as exc:
        raise RuntimeError(f"[STEPS] check_existing_work_item failed for {mva}: {exc}") from exc


async def click_add_work_item(page: Page, mva: str) -> None:
    """Click the 'Add Work Item' button and verify the complaint dialog opened."""
    log.info("[STEPS] %s — clicking 'Add Work Item'", mva)
    try:
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await page.get_by_role("button", name="Add Work Item").click(timeout=10_000)
        # Verify complaint dialog opened — complaint list container must appear
        await page.locator(
            '[class*="fleet-operations-pwa__complaintContainer__"]'
            ', [class*="fleet-operations-pwa__complaintItem__"]'
            ', [class*="fleet-operations-pwa__addComplaint__"]'
        ).first.wait_for(state="visible", timeout=30_000)
        log.info("[STEPS] %s — 'Add Work Item' clicked — complaint dialog opened", mva)
    except Exception as exc:
        raise RuntimeError(f"[STEPS] click_add_work_item failed for {mva}: {exc}") from exc


async def _click_submit_complaint(page: Page, mva: str) -> None:
    """Click Submit Complaint; raises RuntimeError if all click strategies fail."""
    submit_button = page.get_by_role(
        "button", name=re.compile(r"Submit Complaint|Submit", re.I)
    ).first
    await submit_button.wait_for(state="visible", timeout=20_000)

    last_exc: Exception | None = None

    await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
    try:
        await submit_button.click(timeout=8_000)
        return
    except Exception as exc:
        last_exc = exc
        log.warning("[STEPS] %s — submit click failed, retrying with force=True: %s", mva, exc)

    await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
    try:
        await submit_button.click(timeout=8_000, force=True)
        return
    except Exception as exc:
        last_exc = exc
        log.warning("[STEPS] %s — force click failed, retrying via JS evaluate: %s", mva, exc)

    handle = await submit_button.element_handle()
    if handle is None:
        raise RuntimeError(f"[STEPS] {mva} — submit button handle unavailable after 2 failed clicks") from last_exc
    await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
    try:
        await page.evaluate("(el) => el.click()", handle)
    except Exception as exc:
        raise RuntimeError(f"[STEPS] {mva} — all 3 submit click strategies failed") from exc


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


async def handle_complaint_dialog(page: Page, mva: str, type: str, location: str, action: str, step_delay_ms: int = 0) -> None:
    """Associate an existing complaint or create a new one, branching by type (Glass or PM).

    Existing path: find matching complaint tile → click → Next (advances to mileage).
    New path: Add New Complaint → Drivability → type-specific buttons → Submit Complaint.
    Both paths leave the page on the mileage dialog for complete_mileage_dialog().
    """
    log.info("[STEPS] %s — handling complaint dialog (type=%s location=%s action=%s)", mva, type, location, action)

    async def delay():
        if step_delay_ms:
            await page.wait_for_timeout(step_delay_ms)

    try:
        await page.wait_for_timeout(2_000)

        pattern = COMPLAINT_TYPE_PATTERNS.get(type, _GLASS_PATTERN)
        existing_tile = page.locator(
            '[class*="fleet-operations-pwa__complaintItem__"]'
        ).filter(has_text=pattern)

        if await existing_tile.count() > 0:
            log.info("[STEPS] %s — found existing %s complaint, associating", mva, type)
            await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
            await existing_tile.first.click(timeout=5_000);  await delay()
            await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
            await page.get_by_role("button", name="Next").click(timeout=10_000)
            mileage_appeared = False
            for locator in [
                page.get_by_role("heading", name=re.compile(r"Mileage", re.I)),
                page.get_by_text(re.compile(r"\bMileage\b", re.I)),
                page.locator('input[placeholder*="Mileage" i], input[aria-label*="Mileage" i]'),
            ]:
                try:
                    await locator.first.wait_for(state="visible", timeout=8_000)
                    mileage_appeared = True
                    break
                except Exception:
                    continue
            if not mileage_appeared:
                raise RuntimeError(f"[STEPS] {mva} — existing complaint Next did not advance to mileage dialog")
            return

        # No existing complaint — create new
        log.info("[STEPS] %s — no existing %s complaint, creating new", mva, type)
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

        if type == "PM":
            await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
            await page.get_by_role("button", name="PM").click(timeout=10_000)
            log.info("[STEPS] %s PM: PM button clicked", mva);  await delay()

            # Wait for Additional Info screen — leave checkbox at default (unchecked), skip photo
            await page.locator('[class*="fleet-operations-pwa__"]').filter(
                has_text=re.compile(r"additional info", re.I)
            ).first.wait_for(state="visible", timeout=15_000)
            log.info("[STEPS] %s PM: Additional Info screen visible", mva);  await delay()

            pre_submit_url = page.url
            await _click_submit_complaint(page, mva)
            log.info("[STEPS] %s PM: PM complaint submitted", mva)

            if not await _wait_for_post_submit_progress(page, pre_submit_url):
                pm_tile_post = page.locator(
                    '[class*="fleet-operations-pwa__complaintItem__"]'
                ).filter(has_text=_PM_PATTERN)
                if await pm_tile_post.count() > 0:
                    log.info("[STEPS] %s PM: post-submit complaint list shown, associating", mva)
                    await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
                    await pm_tile_post.first.click(timeout=5_000);  await delay()
                    await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
                    await page.get_by_role("button", name="Next").click(timeout=10_000)

                if not await _wait_for_post_submit_progress(page, pre_submit_url):
                    raise RuntimeError(
                        f"[STEPS] {mva} PM — submit completed without mileage/url transition"
                    )
            return

        # Glass path
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
        await page.wait_for_timeout(2_000)
        glass_tile_post = page.locator(
            '[class*="fleet-operations-pwa__complaintItem__"]'
        ).filter(has_text=_GLASS_PATTERN)
        if await glass_tile_post.count() > 0:
            log.info("[STEPS] %s — post-submit: complaint list shown, associating new complaint", mva)
            await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
            await glass_tile_post.first.click(timeout=5_000);  await delay()
            await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
            await page.get_by_role("button", name="Next").click(timeout=10_000)

        if not await _wait_for_post_submit_progress(page, pre_submit_url):
            raise RuntimeError(
                f"[STEPS] {mva} — submit completed without mileage/url transition; backend may have rejected write"
            )

    except Exception as exc:
        raise RuntimeError(f"[STEPS] handle_complaint_dialog failed for {mva}: {exc}") from exc


async def complete_mileage_dialog(page: Page, mva: str) -> None:
    """Advance past the mileage dialog by clicking Next.

    Mirrors mileage_flows.complete_mileage_dialog() — the mileage value is
    typically pre-populated from the vehicle record.
    Verifies the OpCode list appears after Next is clicked.
    """
    log.info("[STEPS] %s — advancing past mileage dialog", mva)
    try:
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await page.get_by_role("button", name="Next").click(timeout=10_000)
        # Verify mileage dialog dismissed — OpCode list must appear
        await page.locator('[class*="opCodeText"]').first.wait_for(state="visible", timeout=15_000)
        log.info("[STEPS] %s — mileage dialog advanced", mva)
    except Exception as exc:
        raise RuntimeError(f"[STEPS] complete_mileage_dialog failed for {mva}: {exc}") from exc


async def select_opcode(page: Page, type: str) -> None:
    """Select the appropriate opcode for the given work item type.

    Glass: selects glass_opcode_primary (default 'Glass Repair/Replace').
    PM: selects pm_opcode config value (default 'PM Gas'); skips step if pm_opcode is null.
    """
    if type == "PM":
        pm_opcode = get_config("pm_opcode", None)
        if pm_opcode is None:
            log.info("[STEPS] PM: pm_opcode is null — skipping opcode selection")
            return
        opcode_label = str(pm_opcode)
    else:
        opcode_label = str(get_config("glass_opcode_primary", "Glass Repair/Replace"))

    log.info("[STEPS] Selecting '%s' OpCode", opcode_label)
    try:
        await page.locator('[class*="opCodeText"]').first.wait_for(
            state="visible", timeout=15_000
        )
        target = page.get_by_text(opcode_label, exact=True)
        await target.scroll_into_view_if_needed()
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await target.click(timeout=10_000)
        await page.get_by_role("button", name="Create Work Item").wait_for(
            state="visible", timeout=15_000
        )
        log.info("[STEPS] OpCode '%s' selected — 'Create Work Item' button visible", opcode_label)
    except Exception as exc:
        raise RuntimeError(f"[STEPS] select_opcode failed for type={type}: {exc}") from exc


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
        # Verify server accepted — Done button must appear on completion dialog
        await page.get_by_role("button", name="Done").wait_for(state="visible", timeout=30_000)
        log.info("[STEPS] 'Create Work Item' confirmed — Done button visible")
    except Exception as exc:
        raise RuntimeError(f"[STEPS] create_work_item failed: {exc}") from exc


async def confirm_completion(page: Page) -> None:
    """Click the final 'Done' button on the completion dialog.

    Verifies the work items list reappears with at least one open item,
    confirming the work item was persisted.
    """
    log.info("[STEPS] Clicking 'Done' button")
    try:
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await page.get_by_role("button", name="Done").click(timeout=10_000)
        # Verify work item persisted — work items container must reappear
        await page.locator(
            "div[class*='fleet-operations-pwa__scan-record__']"
        ).first.wait_for(state="visible", timeout=20_000)
        log.info("[STEPS] 'Done' clicked — work item confirmed in list")
    except Exception as exc:
        raise RuntimeError(f"[STEPS] confirm_completion failed: {exc}") from exc


# ─── Close / Resolve Work Item ────────────────────────────────────────────────

async def open_glass_work_item_tile(page: Page, mva: str) -> None:
    """Click the 'Open' title bar on the glass work item tile to expand the detail card."""
    log.info("[STEPS] %s — opening glass work item tile", mva)
    try:
        tile = page.locator(
            "div[class*='fleet-operations-pwa__scan-record__']"
        ).filter(
            has_text=re.compile(r"glass|windshield|crack|chip|window", re.I)
        ).filter(
            has_text=re.compile(r"open", re.I)
        ).first
        await tile.wait_for(state="visible", timeout=10_000)
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await tile.locator("text=Open").first.click(timeout=8_000)
        # Verify card expanded — "Mark Complete" button must become visible
        await page.get_by_role("button", name="Mark Complete").wait_for(
            state="visible", timeout=15_000
        )
        log.info("[STEPS] %s — glass work item tile opened", mva)
    except Exception as exc:
        raise RuntimeError(f"[STEPS] open_glass_work_item_tile failed for {mva}: {exc}") from exc


async def complete_glass_work_item(page: Page, mva: str, note: str = "Done") -> None:
    """Click 'Mark Complete', fill 'Enter Correction', click 'Complete Work Item'.

    Verifies success by waiting for the tile status to change from 'Open' to 'Complete'.
    """
    log.info("[STEPS] %s — marking glass work item complete", mva)
    try:
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await page.get_by_role("button", name="Mark Complete").click(timeout=10_000)

        correction = page.locator(
            'textarea[placeholder*="Enter Correction"], input[placeholder*="Enter Correction"]'
        ).first
        await correction.wait_for(state="visible", timeout=15_000)
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await correction.click(timeout=5_000)
        await correction.fill(note)

        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await page.get_by_role("button", name="Complete Work Item").click(timeout=10_000)

        # Verify the tile now shows "Complete" instead of "Open"
        await page.locator(
            "div[class*='fleet-operations-pwa__scan-record__']"
        ).filter(
            has_text=re.compile(r"glass|windshield|crack|chip|window", re.I)
        ).filter(
            has_text=re.compile(r"complete", re.I)
        ).first.wait_for(state="visible", timeout=20_000)

        log.info("[STEPS] %s — glass work item marked complete", mva)
    except Exception as exc:
        raise RuntimeError(f"[STEPS] complete_glass_work_item failed for {mva}: {exc}") from exc
