from __future__ import annotations

import argparse
import asyncio
import csv
import os
import re
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from config.config_loader import get_config
from utils.logger import log

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from playwright_prototype.config import (
    resolve_edge_profile_directory,
    resolve_edge_user_data_dir,
    resolve_headless,
    resolve_initial_delay,
    resolve_step_delay,
)
from playwright_prototype.session import ensure_profile_context
from playwright_prototype.steps import warmup_compass as pw_warmup_compass
from playwright_prototype.steps import navigate_to_mva as pw_navigate_to_mva
from playwright_prototype.steps import open_glass_work_item_tile, complete_glass_work_item

if TYPE_CHECKING:
    from playwright.async_api import Page

# Result constants
RESULT_CLOSED = "closed"
RESULT_NOT_FOUND = "not_found"
RESULT_NAV_FAILED = "nav_failed"
RESULT_ERROR = "error"
RESULT_TIMEOUT = "timeout"

_GLASS_PATTERN = re.compile(r"glass|windshield|crack|chip|window", re.I)


def _load_csv(path: str) -> list[dict]:
    """Return rows from a CSV with at minimum an 'mva' column."""
    with open(path, newline="", encoding="utf-8") as f:
        return [row for row in csv.DictReader(f) if row.get("mva", "").strip()]


def _build_targets(args: argparse.Namespace) -> list[str]:
    if args.csv_path:
        rows = _load_csv(args.csv_path)
        targets = [r["mva"].strip() for r in rows]
        log.info("[CLOSE] Loaded %d MVA(s) from %s", len(targets), args.csv_path)
        return targets
    return [args.mva.strip()]


async def _capture_playwright_screenshot(page: "Page", label: str, mva: str) -> None:
    """Save a Playwright screenshot to log/ for debugging."""
    try:
        os.makedirs("log", exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join("log", f"close_{label}_{mva}_{timestamp}.png")
        await page.screenshot(path=path, full_page=True)
        log.info("[CLOSE] Screenshot saved: %s", path)
    except Exception as e:
        log.warning("[CLOSE] Could not capture screenshot: %s", e)


async def _playwright_close_work_item(page: "Page", mva: str) -> tuple[str, str]:
    """Find the open glass work item tile, expand it, and mark it complete.

    Returns (result_constant, tile_detail_text).
    """
    tiles = page.locator("div[class*='fleet-operations-pwa__scan-record__']").filter(
        has_text=_GLASS_PATTERN
    ).filter(
        has_text=re.compile(r"open", re.I)
    )

    count = await tiles.count()
    if count == 0:
        return RESULT_NOT_FOUND, ""

    raw = (await tiles.first.inner_text()).strip()
    detail = " | ".join(line.strip() for line in raw.splitlines() if line.strip())

    await open_glass_work_item_tile(page, mva)
    await complete_glass_work_item(page, mva)

    return RESULT_CLOSED, detail


async def _run_playwright_close_async(args: argparse.Namespace, targets: list[str]) -> list[dict]:
    """Playwright close backend."""
    results: list[dict] = []
    headless = resolve_headless()
    edge_user_data_dir = resolve_edge_user_data_dir()
    edge_profile_directory = resolve_edge_profile_directory()
    step_delay_ms = resolve_step_delay()

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(edge_user_data_dir),
            channel="msedge",
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                f"--profile-directory={edge_profile_directory}",
                "--start-maximized",
            ],
            no_viewport=True,
        )

        try:
            _, page = await ensure_profile_context(context)

            initial_delay_ms = resolve_initial_delay()
            if initial_delay_ms > 0:
                await page.wait_for_timeout(initial_delay_ms)

            await asyncio.wait_for(pw_warmup_compass(page), timeout=args.timeout_seconds)

            for mva in targets:
                log.info("[CLOSE] Settling UI before closing MVA %s (polling every 1s, 10s timeout)...", mva)
                settle_start = time.monotonic()
                settle_timeout = 10.0
                while (time.monotonic() - settle_start) < settle_timeout:
                    try:
                        await page.wait_for_load_state("networkidle", timeout=1_000)
                        log.info("[CLOSE] UI settled")
                        break
                    except (PlaywrightTimeoutError, asyncio.TimeoutError):
                        elapsed = time.monotonic() - settle_start
                        if elapsed < settle_timeout:
                            log.debug("[CLOSE] UI not yet idle (%.1fs elapsed), polling again...", elapsed)
                            continue
                        else:
                            log.warning("[CLOSE] %s - UI settle timeout after %.1fs, proceeding", mva, elapsed)
                            break

                if step_delay_ms > 0:
                    await page.wait_for_timeout(step_delay_ms)

                log.info("[CLOSE] Closing open glass work item for MVA %s...", mva)
                started = time.monotonic()

                try:
                    await asyncio.wait_for(pw_navigate_to_mva(page, mva), timeout=args.timeout_seconds)
                    if step_delay_ms > 0:
                        await page.wait_for_timeout(step_delay_ms)
                except asyncio.TimeoutError:
                    log.error("[CLOSE] %s - timed out after %ss during navigation", mva, args.timeout_seconds)
                    await _capture_playwright_screenshot(page, "timeout", mva)
                    results.append({"mva": mva, "result": RESULT_TIMEOUT, "detail": ""})
                    continue
                except (PlaywrightTimeoutError, Exception) as exc:
                    log.error("[CLOSE] %s - navigation failed, skipping: %s", mva, exc)
                    await _capture_playwright_screenshot(page, "nav_failure", mva)
                    results.append({"mva": mva, "result": RESULT_NAV_FAILED, "detail": ""})
                    continue

                elapsed = time.monotonic() - started
                remaining = max(1.0, args.timeout_seconds - elapsed)

                try:
                    result, detail = await asyncio.wait_for(
                        _playwright_close_work_item(page, mva), timeout=remaining
                    )
                    if result == RESULT_CLOSED:
                        log.info("[CLOSE] %s - CLOSED: glass work item marked complete", mva)
                        if detail:
                            log.info("[CLOSE] %s -   detail: %s", mva, detail)
                        await _capture_playwright_screenshot(page, "closed", mva)
                    elif result == RESULT_NOT_FOUND:
                        log.warning("[CLOSE] %s - NOT FOUND: no open glass work item to close", mva)
                        await _capture_playwright_screenshot(page, "not_found", mva)
                    results.append({"mva": mva, "result": result, "detail": detail})
                except asyncio.TimeoutError:
                    log.error("[CLOSE] %s - timed out after %ss during close", mva, args.timeout_seconds)
                    await _capture_playwright_screenshot(page, "timeout", mva)
                    results.append({"mva": mva, "result": RESULT_TIMEOUT, "detail": ""})
                except Exception as exc:
                    log.error("[CLOSE] %s - error during close: %s", mva, exc)
                    await _capture_playwright_screenshot(page, "error", mva)
                    results.append({"mva": mva, "result": RESULT_ERROR, "detail": ""})
        finally:
            await context.close()
            log.info("[CLOSE] Browser closed.")

    return results


def _run_playwright_close(args: argparse.Namespace, targets: list[str], should_pause: bool) -> list[dict]:
    results = asyncio.run(_run_playwright_close_async(args, targets))
    if should_pause:
        try:
            input("\n[CLOSE] Press Enter to continue...")
        except EOFError:
            pass
    return results


def _log_summary(results: list[dict]) -> tuple[int, int]:
    closed_count = sum(1 for r in results if r["result"] == RESULT_CLOSED)
    not_found_count = sum(1 for r in results if r["result"] == RESULT_NOT_FOUND)
    timeout_count = sum(1 for r in results if r["result"] == RESULT_TIMEOUT)
    failed_count = sum(1 for r in results if r["result"] in {RESULT_NAV_FAILED, RESULT_ERROR, RESULT_TIMEOUT})

    log.info("[CLOSE] %s", "=" * 50)
    log.info("[CLOSE] CLOSE SUMMARY - %d MVA(s)", len(results))
    log.info("[CLOSE]   + Closed:    %d", closed_count)
    log.info("[CLOSE]   - Not found: %d", not_found_count)
    log.info("[CLOSE]   - Timeout:   %d", timeout_count)
    log.info("[CLOSE]   ! Failed:    %d", failed_count)
    log.info("[CLOSE] %s", "=" * 50)
    for r in results:
        status_icon = "+" if r["result"] == RESULT_CLOSED else ("-" if r["result"] == RESULT_NOT_FOUND else "!")
        detail = r.get("detail", "")
        detail_suffix = f"  ({detail})" if detail else ""
        log.info("[CLOSE]   %s  %12s  [%s]%s", status_icon, r["mva"], r["result"], detail_suffix)
    log.info("[CLOSE] %s", "=" * 50)

    return not_found_count, failed_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Close open glass work items for one or more MVAs."
    )
    parser.add_argument("mva", nargs="?", default=None, help="Single target MVA (omit when using --csv)")
    parser.add_argument("--csv", dest="csv_path", default=None, help="Path to CSV file with 'mva' column")
    parser.add_argument("--no-pause", action="store_true", help="Deprecated: no-op kept for backward compatibility")
    parser.add_argument("--pause", action="store_true", help="Prompt for Enter before closing the browser (opt-in)")
    parser.add_argument("--timeout-seconds", type=int, default=90, help="Per-MVA timeout in seconds (default: 90)")

    args = parser.parse_args()

    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be greater than 0")
    if not args.mva and not args.csv_path:
        parser.error("Provide a single MVA positional argument or --csv <path>")
    if args.mva and args.csv_path:
        parser.error("Provide either a single MVA or --csv, not both")

    agentic_env = os.getenv("GLASS_AGENTIC", "").strip().lower() in {"1", "true", "yes"}
    should_pause = sys.stdin.isatty() and args.pause and not agentic_env
    targets = _build_targets(args)

    log.info("[CLOSE] %s", "=" * 50)
    log.info("[CLOSE] Glass work item close — %d MVA(s)", len(targets))
    log.info("[CLOSE] %s", "=" * 50)

    results = _run_playwright_close(args, targets, should_pause)

    not_found_count, failed_count = _log_summary(results)
    if not_found_count > 0 or failed_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
