# GlassWorkItems.py — Phase 7 standalone entry point
# Run after Phase 1-6 and after operator has reviewed/filled Location column.
#
# Usage: .venv\Scripts\python.exe GlassWorkItems.py
#        or: Run-GlassWorkItems.cmd

import os
import sys
import gspread

from core.driver_manager import create_driver, quit_driver
from config.config_loader import get_config
from flows.LoginFlow import LoginFlow
from flows.glass_work_item_phase import read_glass_claims, run_glass_work_item_phase
from utils.logger import log

SERVICE_ACCOUNT_JSON = get_config("service_account_json", "Service_account.json")
SPREADSHEET_ID = get_config("spreadsheet_id")
SHEET_NAME = get_config("sheet_name", "GlassClaims")


def main():
    username = os.getenv("GLASS_LOGIN_USERNAME") or get_config("username")
    password = os.getenv("GLASS_LOGIN_PASSWORD") or get_config("password")
    login_id = os.getenv("GLASS_LOGIN_ID") or get_config("login_id")

    driver = create_driver()
    try:
        # Login
        login_flow = LoginFlow(driver)
        login_result = login_flow.login_handler(username, password, login_id)
        if login_result.get("status") != "ok":
            log.error(f"[PHASE7] Login failed: {login_result}")
            return

        # Connect to Google Sheet
        gc = gspread.service_account(filename=SERVICE_ACCOUNT_JSON)
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(SHEET_NAME)

        # Build manifest
        manifest = read_glass_claims(ws)
        log.info(f"[PHASE7] {len(manifest)} eligible MVA(s) to process")

        if not manifest:
            log.info("[PHASE7] No eligible MVAs found — nothing to do.")
            return

        # Run phase
        summary = run_glass_work_item_phase(driver, manifest, sheet_client=None, tab_name=SHEET_NAME)
        log.info(f"[PHASE7] Complete — {summary}")

    finally:
        quit_driver()
        log.info("[PHASE7] Browser closed.")


if __name__ == "__main__":
    main()
