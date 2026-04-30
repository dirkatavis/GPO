# verify_workitem.py — Verify that one or more MVAs have a specific open work item type
#
# Usage:
#   Single MVA — check for any GLASS work item (default):
#     .venv\Scripts\python.exe verify_workitem.py 59231211
#
#   Single MVA — check for a specific type:
#     .venv\Scripts\python.exe verify_workitem.py 59231211 --type "Glass Replacement"
#     .venv\Scripts\python.exe verify_workitem.py 59231211 --type "Glass Repair"
#
#   Batch via CSV (column: mva, optional column: type):
#     .venv\Scripts\python.exe verify_workitem.py --csv playwright_prototype/sample_mvas.csv
#     .venv\Scripts\python.exe verify_workitem.py --csv data/GlassDataParser.csv --type GLASS
#
# Supported work item type keywords (case-insensitive match against tile text):
#   GLASS          — matches any glass work item
#   Glass Replacement
#   Glass Repair
#   PM             — preventive maintenance
#   (any keyword that appears in the Compass work item tile text)
#
# Does NOT modify Compass in any way — read-only.

import sys
import os
import csv
import argparse

from core.driver_manager import create_driver, quit_driver
from config.config_loader import get_config
from flows.LoginFlow import LoginFlow
from flows.mva_navigation import warmup_compass, navigate_to_mva
from flows.work_item_flow import check_existing_work_item
from utils.logger import log


# Result constants
RESULT_FOUND = "found"
RESULT_NOT_FOUND = "not_found"
RESULT_NAV_FAILED = "nav_failed"
RESULT_ERROR = "error"


def _load_csv(path: str) -> list[dict]:
    """Return rows from a CSV with at minimum an 'mva' column."""
    with open(path, newline="", encoding="utf-8") as f:
        return [row for row in csv.DictReader(f) if row.get("mva", "").strip()]


def _capture_screenshot(driver, label: str, mva: str) -> None:
    """Save a screenshot to log/ for debugging."""
    import time
    try:
        os.makedirs("log", exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join("log", f"verify_{label}_{mva}_{timestamp}.png")
        driver.save_screenshot(path)
        log.info(f"[VERIFY] Screenshot saved: {path}")
    except Exception as e:
        log.warning(f"[VERIFY] Could not capture screenshot: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Verify that open work items of a given type exist for one or more MVAs. Read-only."
    )
    parser.add_argument(
        "mva",
        nargs="?",
        default=None,
        help="Single target MVA (omit when using --csv)",
    )
    parser.add_argument(
        "--csv",
        dest="csv_path",
        default=None,
        help="Path to CSV file with 'mva' column and optional 'type' column",
    )
    parser.add_argument(
        "--type",
        dest="work_item_type",
        default="glass damage",
        help="Work item type keyword to match in tile text (default: 'glass damage'). "
             "Examples: 'glass damage', 'Windshield Crack', 'Windshield Chip', 'Side/Rear Window Damage'",
    )
    parser.add_argument(
        "--no-pause",
        action="store_true",
        help="Do not prompt for Enter before browser close",
    )
    args = parser.parse_args()

    if not args.mva and not args.csv_path:
        parser.error("Provide a single MVA positional argument or --csv <path>")
    if args.mva and args.csv_path:
        parser.error("Provide either a single MVA or --csv, not both")

    agentic_env = os.getenv("GLASS_AGENTIC", "").strip().lower() in {"1", "true", "yes"}
    should_pause = sys.stdin.isatty() and not args.no_pause and not agentic_env

    # Build list of (mva, work_item_type) tuples
    if args.csv_path:
        rows = _load_csv(args.csv_path)
        targets = [
            (r["mva"].strip(), r.get("type", args.work_item_type).strip() or args.work_item_type)
            for r in rows
        ]
        log.info(f"[VERIFY] Loaded {len(targets)} MVA(s) from {args.csv_path}")
    else:
        targets = [(args.mva.strip(), args.work_item_type)]

    log.info(f"[VERIFY] {'=' * 50}")
    log.info(f"[VERIFY] Work item verification — {len(targets)} MVA(s)")
    log.info(f"[VERIFY] Default type filter: {args.work_item_type}")
    log.info(f"[VERIFY] {'=' * 50}")

    username = os.getenv("GLASS_LOGIN_USERNAME") or get_config("username")
    password = os.getenv("GLASS_LOGIN_PASSWORD") or get_config("password")
    login_id = os.getenv("GLASS_LOGIN_ID") or get_config("login_id")

    driver = create_driver()
    results: list[dict] = []

    try:
        # Login once
        login_flow = LoginFlow(driver)
        login_result = login_flow.login_handler(username, password, login_id)
        if login_result.get("status") != "ok":
            log.error(f"[VERIFY] Login failed: {login_result}")
            _capture_screenshot(driver, "login_failure", "batch")
            sys.exit(1)
        log.info("[VERIFY] Login OK")

        # Warm up Compass once
        if not warmup_compass(driver):
            log.error("[VERIFY] Compass warm-up failed — aborting")
            _capture_screenshot(driver, "warmup_failure", "batch")
            sys.exit(1)

        for mva, work_item_type in targets:
            log.info(f"[VERIFY] Checking MVA {mva} for open '{work_item_type}' work item...")

            if not navigate_to_mva(driver, mva):
                log.error(f"[VERIFY] {mva} — navigation failed, skipping")
                _capture_screenshot(driver, "nav_failure", mva)
                results.append({"mva": mva, "type": work_item_type, "result": RESULT_NAV_FAILED})
                continue

            try:
                found = check_existing_work_item(driver, mva, work_item_type=work_item_type)
                if found:
                    log.info(f"[VERIFY] {mva} — ✓ FOUND: open '{work_item_type}' work item confirmed")
                    _capture_screenshot(driver, "found", mva)
                    results.append({"mva": mva, "type": work_item_type, "result": RESULT_FOUND})
                else:
                    log.warning(f"[VERIFY] {mva} — ✗ NOT FOUND: no open '{work_item_type}' work item")
                    _capture_screenshot(driver, "not_found", mva)
                    results.append({"mva": mva, "type": work_item_type, "result": RESULT_NOT_FOUND})
            except Exception as e:
                log.error(f"[VERIFY] {mva} — error during check: {e}")
                _capture_screenshot(driver, "error", mva)
                results.append({"mva": mva, "type": work_item_type, "result": RESULT_ERROR})

    finally:
        if should_pause:
            try:
                input("\n[VERIFY] Press Enter to close the browser...")
            except EOFError:
                pass
        quit_driver()
        log.info("[VERIFY] Browser closed.")

    # Summary
    found_count = sum(1 for r in results if r["result"] == RESULT_FOUND)
    not_found_count = sum(1 for r in results if r["result"] == RESULT_NOT_FOUND)
    failed_count = sum(1 for r in results if r["result"] in {RESULT_NAV_FAILED, RESULT_ERROR})

    log.info(f"[VERIFY] {'=' * 50}")
    log.info(f"[VERIFY] VERIFICATION SUMMARY — {len(results)} MVA(s)")
    log.info(f"[VERIFY]   ✓ Found:     {found_count}")
    log.info(f"[VERIFY]   ✗ Not found: {not_found_count}")
    log.info(f"[VERIFY]   ! Failed:    {failed_count}")
    log.info(f"[VERIFY] {'=' * 50}")
    for r in results:
        status_icon = "✓" if r["result"] == RESULT_FOUND else ("✗" if r["result"] == RESULT_NOT_FOUND else "!")
        log.info(f"[VERIFY]   {status_icon}  {r['mva']:>12}  [{r['type']}]  →  {r['result']}")
    log.info(f"[VERIFY] {'=' * 50}")

    # Exit non-zero if any MVA was not found or failed
    if not_found_count > 0 or failed_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
