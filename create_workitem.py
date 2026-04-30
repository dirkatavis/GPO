# create_workitem.py — Batch work item creation with persistent session
#
# Usage:
#   Create work items from CSV in single session:
#     .venv\Scripts\python.exe create_workitem.py --csv data.csv --backend playwright
#
#   Create single MVA:
#     .venv\Scripts\python.exe create_workitem.py 59257306 --backend playwright
#

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import sys
from pathlib import Path

from utils.logger import log

from playwright.async_api import async_playwright
from playwright_prototype.config import (
    resolve_edge_profile_directory,
    resolve_edge_user_data_dir,
    resolve_headless,
    resolve_initial_delay,
    resolve_step_delay,
)
from playwright_prototype.main import process_mva
from playwright_prototype.session import ensure_profile_context
from playwright_prototype.steps import (
    ExistingWorkItemError,
    check_existing_glass_work_item,
    navigate_to_mva as pw_navigate_to_mva,
    warmup_compass as pw_warmup_compass,
)


def _resolve_row_work_item_action(row: dict, default_action: str) -> str:
    """Resolve action (Replace/Repair) from CSV row, with fallback to default."""
    if "action" in row and row["action"].strip():
        action = row["action"].strip()
        if action.lower() in ["replace", "repair"]:
            return action.lower().capitalize()
    return default_action


def _build_create_targets(args) -> list[dict]:
    """Build list of (mva, location, action) targets from CLI args."""
    targets = []

    if args.csv:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            log.error("[CREATE] CSV file not found: %s", csv_path)
            sys.exit(1)

        with open(csv_path) as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "mva" not in reader.fieldnames:
                log.error("[CREATE] CSV missing required 'mva' column")
                sys.exit(1)

            default_action = args.action or "Replace"
            for i, row in enumerate(reader, start=2):  # start=2 to account for header
                mva = row.get("mva", "").strip()
                if not mva:
                    log.warning("[CREATE] Row %d: empty MVA, skipping", i)
                    continue

                location = row.get("location", "WS").strip() or "WS"
                action = _resolve_row_work_item_action(row, default_action)

                targets.append({
                    "mva": mva,
                    "location": location,
                    "action": action,
                })

        log.info("[CREATE] Loaded %d MVA(s) from %s", len(targets), csv_path)
    else:
        # Single MVA from CLI
        targets.append({
            "mva": args.mva,
            "location": args.location or "WS",
            "action": args.action or "Replace",
        })

    return targets


async def _run_playwright_creation_async(targets: list[dict]) -> None:
    """Create multiple work items in a single persistent session."""
    headless = resolve_headless()
    edge_user_data_dir = resolve_edge_user_data_dir()
    edge_profile_directory = resolve_edge_profile_directory()
    step_delay_ms = resolve_step_delay()

    log.info("[CREATE] %s", "=" * 50)
    log.info("[CREATE] Work item creation - %d MVA(s)", len(targets))
    log.info("[CREATE] Backend: playwright")
    log.info("[CREATE] %s", "=" * 50)

    created_count = 0
    skipped_count = 0
    failed_count = 0

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

            # Warm up Compass once
            log.info("[CREATE] Warming up Compass with dummy MVA 50227203...")
            await pw_warmup_compass(page)
            log.info("[CREATE] Compass warm-up complete")

            # Create each MVA in sequence
            for target in targets:
                mva = target["mva"]
                location = target["location"]
                action = target["action"]

                try:
                    log.info("[CREATE] Processing MVA %s (location=%s, action=%s)...", mva, location, action)

                    # Navigate to MVA
                    await pw_navigate_to_mva(page, mva)

                    # Check for existing work item
                    try:
                        await check_existing_glass_work_item(page, mva)
                        existing = False
                    except ExistingWorkItemError:
                        existing = True

                    if existing:
                        log.info("[CREATE] %s — SKIP: existing work item found", mva)
                        skipped_count += 1
                        continue

                    # Create work item
                    log.info("[CREATE] %s — Creating work item...", mva)
                    await process_mva(page, mva, location=location, action=action, step_delay_ms=step_delay_ms)
                    log.info("[CREATE] %s — ✓ Created", mva)
                    created_count += 1

                except Exception as e:
                    log.error("[CREATE] %s — ✗ FAILED: %s", mva, str(e))
                    failed_count += 1
                    continue

            await context.close()
            log.info("[CREATE] Browser closed.")

        except Exception as e:
            log.error("[CREATE] Session error: %s", str(e))
            await context.close()
            sys.exit(1)

    log.info("[CREATE] %s", "=" * 50)
    log.info("[CREATE] CREATION SUMMARY - %d MVA(s)", len(targets))
    log.info("[CREATE]   ✓ Created:  %d", created_count)
    log.info("[CREATE]   - Skipped:  %d", skipped_count)
    log.info("[CREATE]   ✗ Failed:   %d", failed_count)
    log.info("[CREATE] %s", "=" * 50)

    if failed_count > 0 or (created_count == 0 and skipped_count == 0):
        sys.exit(1)


def _selenium_create(targets: list[dict]) -> None:
    """Selenium backend placeholder."""
    log.error("[CREATE] Selenium backend for batch create not yet implemented")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Create work items in batch with persistent session"
    )
    parser.add_argument(
        "mva",
        nargs="?",
        help="Single MVA to create (omit if using --csv)"
    )
    parser.add_argument(
        "--csv",
        help="CSV file with columns: mva,location,action"
    )
    parser.add_argument(
        "--location",
        default="WS",
        help="Location code (e.g., WS, APO, BB) — default: WS"
    )
    parser.add_argument(
        "--action",
        choices=["Replace", "Repair"],
        help="Work item action (Replace or Repair)"
    )
    parser.add_argument(
        "--backend",
        choices=["selenium", "playwright"],
        default="playwright",
        help="Browser backend — default: playwright"
    )

    args = parser.parse_args()

    # Validate input
    if not args.mva and not args.csv:
        parser.error("Either provide MVA or use --csv")
    if args.mva and args.csv:
        parser.error("Cannot use both MVA and --csv together")

    targets = _build_create_targets(args)

    if not targets:
        log.error("[CREATE] No targets to process")
        sys.exit(1)

    if args.backend == "playwright":
        asyncio.run(_run_playwright_creation_async(targets))
    else:
        _selenium_create(targets)


if __name__ == "__main__":
    main()
