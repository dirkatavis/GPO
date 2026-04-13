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
import time

from core.driver_manager import create_driver, quit_driver
from config.config_loader import get_config
from flows.LoginFlow import LoginFlow
from flows.work_item_flow import check_existing_work_item
from pages.mva_input_page import MVAInputPage
from pages.vehicle_properties_page import VehiclePropertiesPage
from utils.logger import log
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def wait_for_mva_input(driver, timeout: int = 30):
    """Wait until the MVA input field is present and clickable — app fully initialized."""
    log.info(f"[SMOKE] Waiting for Compass app to be ready (up to {timeout}s)...")
    for locator in MVAInputPage.CANDIDATES:
        try:
            field = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable(locator)
            )
            log.info(f"[SMOKE] App ready — MVA input field is clickable")
            return field
        except Exception:
            continue
    return None


def navigate_to_mva(driver, mva: str) -> bool:
    """Type the MVA into the Compass search field and wait for the page to load."""
    try:
        # Wait for app to be fully ready before touching the input
        input_field = wait_for_mva_input(driver)
        if not input_field:
            log.error(f"[SMOKE] MVA input field never became clickable — app did not initialize")
            return False

        # Warm-up: send a dummy value to trigger Compass app initialization,
        # then wait briefly before entering the real MVA. The input becomes
        # clickable before the app is fully ready — this replicates the
        # manual workaround of entering a throwaway MVA and waiting ~5s.
        log.info(f"[SMOKE] Warming up Compass app...")
        input_field.clear()
        input_field.send_keys("00000000")
        time.sleep(5)
        input_field.clear()
        time.sleep(0.5)

        # Now enter the real MVA
        input_field.send_keys(mva)
        log.info(f"[SMOKE] Entered MVA: {mva}")

        # Wait for the page to be loaded — use "Add Work Item" button as the
        # anchor since it's always present regardless of whether work items exist.
        # (scan-record__ only renders when work items are present, so it can't
        # be used as a readiness signal for MVAs with 0 work items.)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (By.XPATH, "//button[normalize-space()='Add Work Item']")
            )
        )

        # Validate the MVA detail panel loaded (plate, VIN, Desc, etc.)
        # Bad state: panel is missing — Compass accepted the input but didn't
        # navigate to the vehicle, meaning the app wasn't fully ready.
        props_page = VehiclePropertiesPage(driver)
        last8 = mva[-8:] if len(mva) >= 8 else mva
        echo = props_page.find_mva_echo(last8, timeout=10)
        if not echo:
            log.error(
                f"[SMOKE] Vehicle detail panel not found for {mva} — "
                f"Compass accepted the MVA but did not load vehicle properties. "
                f"The app may not have been fully initialized."
            )
            return False

        log.info(f"[SMOKE] MVA page loaded for {mva} — vehicle detail panel confirmed")
        return True
    except Exception as e:
        log.error(f"[SMOKE] Navigation to {mva} failed: {e}")
        return False


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

        # Step 2: Navigate to MVA
        log.info(f"[SMOKE] Step 2 — Navigating to MVA {mva}...")
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
