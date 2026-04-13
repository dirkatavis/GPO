# smoke_test_workitem.py — Phase 7 smoke test for a single MVA
#
# Usage:
#   Check only (safe — no changes to Compass):
#     .venv\Scripts\python.exe smoke_test_workitem.py 59257306
#
#   Check + create (writes a real work item to Compass):
#     .venv\Scripts\python.exe smoke_test_workitem.py 59257306 --create
#
# Does NOT read from or write to the Google Sheet.

import sys
import os

from core.driver_manager import create_driver, quit_driver
from config.config_loader import get_config
from flows.LoginFlow import LoginFlow
from flows.mva_navigation import warmup_compass, navigate_to_mva
from flows.work_item_flow import check_existing_work_item
from utils.logger import log


def main():
    if len(sys.argv) < 2:
        print("Usage: python smoke_test_workitem.py <MVA> [--create]")
        sys.exit(1)

    mva = sys.argv[1].strip()
    do_create = "--create" in sys.argv

    log.info(f"[SMOKE] {'=' * 50}")
    log.info(f"[SMOKE] Smoke test starting — MVA: {mva}")
    log.info(f"[SMOKE] Mode: {'CHECK + CREATE' if do_create else 'CHECK ONLY (read-only)'}")
    log.info(f"[SMOKE] {'=' * 50}")

    username = os.getenv("GLASS_LOGIN_USERNAME") or get_config("username")
    password = os.getenv("GLASS_LOGIN_PASSWORD") or get_config("password")
    login_id = os.getenv("GLASS_LOGIN_ID") or get_config("login_id")

    driver = create_driver()
    try:
        # Step 1: Login
        log.info(f"[SMOKE] Step 1 — Logging in...")
        login_flow = LoginFlow(driver)
        result = login_flow.login_handler(username, password, login_id)
        if result.get("status") != "ok":
            log.error(f"[SMOKE] Login failed: {result}")
            sys.exit(1)
        log.info(f"[SMOKE] Login OK")

        # Step 2: Warm up Compass, then navigate to MVA
        log.info(f"[SMOKE] Step 2 — Warming up Compass and navigating to MVA {mva}...")
        if not warmup_compass(driver):
            log.error(f"[SMOKE] Compass warm-up failed — aborting")
            sys.exit(1)
        if not navigate_to_mva(driver, mva):
            log.error(f"[SMOKE] Could not navigate to MVA — aborting")
            sys.exit(1)

        # Step 3: Check for existing work item
        log.info(f"[SMOKE] Step 3 — Checking for existing open glass work item...")
        has_existing = check_existing_work_item(driver, mva, work_item_type="GLASS")
        log.info(f"[SMOKE] Result: existing open glass work item = {has_existing}")

        if has_existing:
            log.info(f"[SMOKE] ✓ SKIP path confirmed — work item already exists, nothing to create")
            if do_create:
                log.info(f"[SMOKE] --create flag ignored because existing work item was found")
            return

        log.info(f"[SMOKE] No existing work item found")

        if not do_create:
            log.info(f"[SMOKE] CHECK ONLY mode — stopping here. Run with --create to test creation.")
            return

        # Step 4: Create work item
        log.info(f"[SMOKE] Step 4 — Creating glass work item for {mva}...")
        from flows.work_item_handler import WorkItemConfig, create_work_item_handler
        config = WorkItemConfig(mva=mva, damage_type="Replacement", location="WINDSHIELD")
        handler = create_work_item_handler("GLASS", driver)
        result = handler.create_work_item(config)

        log.info(f"[SMOKE] {'=' * 50}")
        if result.get("status") == "created":
            log.info(f"[SMOKE] ✓ SUCCESS — work item created for {mva}")
        else:
            log.error(f"[SMOKE] ✗ FAILED — result: {result}")
        log.info(f"[SMOKE] {'=' * 50}")

    finally:
        if sys.stdin.isatty():
            try:
                input("\n[SMOKE] Press Enter to close the browser...")
            except EOFError:
                pass
        quit_driver()
        log.info(f"[SMOKE] Browser closed.")


if __name__ == "__main__":
    main()
