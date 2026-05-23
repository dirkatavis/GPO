from __future__ import annotations

import datetime
import logging
import re
import time
from typing import TYPE_CHECKING

from config.config_loader import get_config

_GLASS_PATTERN = re.compile(r"glass|windshield|crack|chip|window", re.I)
_PM_PATTERN = re.compile(r"\bpm\b(?:\s+gas)?\b", re.I)

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


def _is_unready_vehicle_value(value: str | None) -> bool:
    """Return True when a vehicle-property value is not yet populated."""
    stripped = (value or "").strip()
    if not stripped:
        return True
    return bool(re.fullmatch(r"[-\u2010\u2011\u2012\u2013\u2014\u2015\s]+", stripped))


def _normalize_digits(value: str) -> str:
    """Return only numeric characters from the provided string."""
    return re.sub(r"\D", "", value or "")


async def _wait_for_vehicle_details_ready(page: Page, mva: str, timeout_ms: int = 20_000) -> None:
    """Wait until the vehicle details panel shows a populated MVA value for the target MVA."""
    last8 = mva[-8:] if len(mva) >= 8 else mva
    value_locator = page.locator(
        "xpath="
        "//div[contains(@class,'vehicle-properties-container')]"
        "//div[contains(@class,'vehicle-property__')]"
        "[div[contains(@class,'vehicle-property-name')][normalize-space()='MVA']]"
        "/div[contains(@class,'vehicle-property-value')]"
    ).first

    deadline = time.monotonic() + (timeout_ms / 1000.0)
    last_seen = ""
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            raw_value = (await value_locator.inner_text()).strip()
            last_seen = raw_value
            last_error = None
            if not _is_unready_vehicle_value(raw_value):
                digits = _normalize_digits(raw_value)
                if last8 in raw_value or last8 in digits:
                    log.info("[STEPS] %s — vehicle details ready (MVA=%s)", mva, raw_value)
                    return
        except Exception as exc:
            last_error = exc
            log.debug("[STEPS] %s — readiness probe retry due to locator/read error: %s", mva, exc)
        await page.wait_for_timeout(400)

    extra = f"; last_error={last_error!r}" if last_error is not None else ""
    raise RuntimeError(
        f"[STEPS] {mva} — vehicle details not ready; MVA value stayed empty/hyphen or mismatched"
        f" (last_seen={last_seen!r}){extra}"
    )


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
        try:
            await _wait_for_vehicle_details_ready(page, dummy_mva, timeout_ms=20_000)
        except Exception as exc:
            log.warning("[STEPS] Warm-up: vehicle details not fully confirmed (%s) — proceeding anyway", exc)
        log.info("[STEPS] Compass warm-up complete")
    except Exception:
        log.warning("[STEPS] Warm-up: 'Add Work Item' not confirmed within timeout — proceeding anyway")


async def navigate_to_mva(page: Page, mva: str) -> None:
    """Enter an MVA and wait for the vehicle page to fully load.

    Waits for 'Add Work Item' to be enabled, then confirms the vehicle detail
    panel has a populated MVA value matching the requested MVA.
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
        await _wait_for_vehicle_details_ready(page, mva, timeout_ms=25_000)
        log.info("[STEPS] %s — vehicle page loaded", mva)
    except Exception as exc:
        raise RuntimeError(f"[STEPS] navigate_to_mva failed for {mva}: {exc}") from exc


# ─── Work Item Flow ───────────────────────────────────────────────────────────

class ExistingWorkItemError(Exception):
    """Raised when an open work item of the requested type already exists for an MVA."""


def _parse_tile_created_at(tile_text: str) -> datetime.date | None:
    """Extract and parse the Created At date from a work item tile's inner text.

    Returns a date object or None if the field is absent or unparseable.
    Expected format: 'Created At: M/D/YYYY, H:MM:SS AM/PM'
    """
    match = re.search(r"Created At:\s*(\d{1,2}/\d{1,2}/\d{4})", tile_text, re.I)
    if not match:
        return None
    try:
        return datetime.datetime.strptime(match.group(1), "%m/%d/%Y").date()
    except ValueError:
        return None


def _extract_complaints_text(tile_text: str) -> str:
    """Extract complaint text from a tile, returning empty string if absent."""
    for line in tile_text.splitlines():
        match = re.search(r"complaints\s*:\s*(.+)", line, re.I)
        if match:
            return match.group(1).strip()
    return ""


def _tile_matches_complaint_type(tile_text: str, pattern: re.Pattern) -> bool:
    """Match complaint type using only the complaints row to avoid timestamp false positives."""
    complaints = _extract_complaints_text(tile_text)
    return bool(complaints and pattern.search(complaints))


async def check_existing_work_item(page: Page, mva: str, complaint_type: str) -> None:
    """Raise ExistingWorkItemError when a same-type existing work item should block creation.

    Decision rules:
    - Any open same-type work item blocks creation, regardless of age.
    - Otherwise, a same-type work item created within duplicate_window_days blocks creation.
    - If Created At is missing for a same-type tile, treat as duplicate to avoid false creates.
    """
    pattern = COMPLAINT_TYPE_PATTERNS.get(complaint_type, _GLASS_PATTERN)
    window_days = int(get_config("duplicate_window_days", 5))
    log.info("[STEPS] %s — checking for existing %s work item (window=%d days)", mva, complaint_type, window_days)
    try:
        container = page.locator('[class*="fleet-operations-pwa__scan-record__"]').first
        try:
            await container.wait_for(state="visible", timeout=8_000)
        except Exception:
            log.info("[STEPS] %s — no work items container found, safe to proceed", mva)
            return

        all_tiles = page.locator('[class*="fleet-operations-pwa__scan-record__"]')
        count = await all_tiles.count()
        today = datetime.date.today()
        for idx in range(count):
            tile_text = await all_tiles.nth(idx).inner_text()
            if not _tile_matches_complaint_type(tile_text, pattern):
                continue

            if re.search(r"^\s*open\b", tile_text, re.I | re.M):
                raise ExistingWorkItemError(
                    f"{mva} — open {complaint_type} work item already exists: {tile_text.strip()!r}"
                )

            created_at = _parse_tile_created_at(tile_text)
            if created_at is None:
                log.warning("[STEPS] %s — %s tile has no Created At; treating as duplicate", mva, complaint_type)
                raise ExistingWorkItemError(
                    f"{mva} — {complaint_type} work item already exists (no date): {tile_text.strip()!r}"
                )

            age_days = (today - created_at).days
            if window_days == 0 or age_days <= window_days:
                raise ExistingWorkItemError(
                    f"{mva} — {complaint_type} work item already exists (created {age_days}d ago): {tile_text.strip()!r}"
                )
            log.info("[STEPS] %s — %s tile found but is %d days old (> window %d) — ignoring", mva, complaint_type, age_days, window_days)
        log.info("[STEPS] %s — no blocking %s work item found, safe to proceed", mva, complaint_type)
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


async def handle_complaint_dialog(page: Page, mva: str, complaint_type: str, location: str, action: str, step_delay_ms: int = 0) -> None:
    """Associate an existing complaint or create a new one, branching by type (Glass or PM).

    Existing path: find matching complaint tile → click → Next (advances to mileage).
    New path: Add New Complaint → Drivability → type-specific buttons → Submit Complaint.
    Both paths leave the page on the mileage dialog for complete_mileage_dialog().
    """
    log.info("[STEPS] %s — handling complaint dialog (type=%s location=%s action=%s)", mva, complaint_type, location, action)

    async def delay():
        if step_delay_ms:
            await page.wait_for_timeout(step_delay_ms)

    try:
        await page.wait_for_timeout(2_000)

        pattern = COMPLAINT_TYPE_PATTERNS.get(complaint_type, _GLASS_PATTERN)
        existing_tile = page.locator(
            '[class*="fleet-operations-pwa__complaintItem__"]'
        ).filter(has_text=pattern)

        if await existing_tile.count() > 0:
            log.info("[STEPS] %s — found existing %s complaint, associating", mva, complaint_type)
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
        log.info("[STEPS] %s — no existing %s complaint, creating new", mva, complaint_type)
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

        if complaint_type == "PM":
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


async def select_opcode(page: Page, complaint_type: str) -> None:
    """Select the appropriate opcode for the given work item type.

    Glass: selects glass_opcode_primary (default 'Glass Repair/Replace').
    PM: selects pm_opcode config value (default 'PM Gas'); skips step if pm_opcode is null.
    """
    if complaint_type == "PM":
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
        raise RuntimeError(f"[STEPS] select_opcode failed for complaint_type={complaint_type}: {exc}") from exc


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

async def open_work_item_tile(page: Page, mva: str, complaint_type: str = "Glass") -> None:
    """Click the matching open work item tile and verify details are shown."""
    log.info("[STEPS] %s — opening %s work item tile", mva, complaint_type)
    pattern = COMPLAINT_TYPE_PATTERNS.get(complaint_type, _GLASS_PATTERN)
    try:
        open_tiles = page.locator(
            "div[class*='fleet-operations-pwa__scan-record__']"
        ).filter(
            has_text=re.compile(r"open", re.I)
        )

        count = await open_tiles.count()
        if count == 0:
            raise RuntimeError(f"[STEPS] {mva} — no open work item tiles found")

        for idx in range(count):
            tile = open_tiles.nth(idx)
            tile_text = (await tile.inner_text()).strip()
            if not _tile_matches_complaint_type(tile_text, pattern):
                continue

            await tile.wait_for(state="visible", timeout=10_000)
            await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
            await tile.locator("text=Open").first.click(timeout=8_000)
            await page.get_by_role("button", name="Mark Complete").wait_for(
                state="visible", timeout=15_000
            )
            log.info("[STEPS] %s — %s work item tile opened", mva, complaint_type)
            return

        raise RuntimeError(f"[STEPS] {mva} — no open {complaint_type} tile matched complaints row")
    except Exception as exc:
        raise RuntimeError(f"[STEPS] open_work_item_tile failed for {mva}: {exc}") from exc


async def open_glass_work_item_tile(page: Page, mva: str, complaint_type: str = "Glass", **kwargs) -> None:
    """Backward-compatible wrapper for open_work_item_tile()."""
    legacy_type = kwargs.get("type")
    await open_work_item_tile(page, mva, complaint_type=legacy_type or complaint_type)


async def complete_work_item(page: Page, mva: str, note: str = "Done", complaint_type: str = "Glass") -> None:
    """Click 'Mark Complete', fill correction, and complete the selected work item."""
    log.info("[STEPS] %s — marking %s work item complete", mva, complaint_type)
    pattern = COMPLAINT_TYPE_PATTERNS.get(complaint_type, _GLASS_PATTERN)
    try:
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await page.get_by_role("button", name="Mark Complete").click(timeout=10_000)

        correction = page.locator(
            'textarea[class*="textAreaContainer"], '
            'textarea[placeholder*="Enter Correction"], input[placeholder*="Enter Correction"]'
        ).first
        await correction.wait_for(state="visible", timeout=15_000)
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await correction.click(timeout=5_000)
        await correction.fill(note)

        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await page.get_by_role("button", name="Complete Work Item").click(timeout=10_000)

        await page.locator(
            "div[class*='fleet-operations-pwa__scan-record__']"
        ).filter(
            has_text=pattern
        ).filter(
            has_text=re.compile(r"complete", re.I)
        ).first.wait_for(state="visible", timeout=20_000)

        log.info("[STEPS] %s — %s work item marked complete", mva, complaint_type)
    except Exception as exc:
        raise RuntimeError(f"[STEPS] complete_work_item failed for {mva}: {exc}") from exc


async def complete_glass_work_item(page: Page, mva: str, note: str = "Done", complaint_type: str = "Glass", **kwargs) -> None:
    """Backward-compatible wrapper for complete_work_item()."""
    legacy_type = kwargs.get("type")
    await complete_work_item(page, mva, note=note, complaint_type=legacy_type or complaint_type)
