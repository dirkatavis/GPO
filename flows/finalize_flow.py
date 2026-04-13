import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from utils.logger import log
from utils.ui_helpers import click_element, navigate_back_to_home, save_failure_screenshot


def finalize_workitem(driver, mva: str) -> dict:
    """
    Finalize the Work Item creation process.
    Steps:
      1. Click 'Create Work Item'
      2. Verify Work Item tile is present
      3. Click 'Done' to return to the MVA page

    Returns {"status": "created"} on success. Glass work items are left Open —
    they are not marked complete here; that is the technician's responsibility.
    """
    log.debug(f"[FINALIZE] {mva} - Finalizing work item.")
    try:
        # Step 1: Click Create Work Item
        if not click_element(driver, (By.XPATH, "//button[normalize-space()='Create Work Item']")):
            log.warning(f"[WORKITEM][WARN] {mva} - 'Create Work Item' button not found")
            save_failure_screenshot(driver, mva, "create_work_item")
            return {"status": "failed", "reason": "create_btn", "mva": mva}

        log.info(f"[FLOW] {mva} - Click Create Work Item button — PASSED")
        time.sleep(2)  # allow UI to update

        # Step 2: Verify Work Item exists
        tiles = driver.find_elements(By.XPATH, "//div[contains(@class,'scan-record-header')]")
        if not tiles:
            log.warning(f"[WORKITEM][WARN] {mva} - no Work Item tiles found after creation")
            save_failure_screenshot(driver, mva, "no_work_item_tiles")
            return {"status": "failed", "reason": "no_tiles", "mva": mva}

        log.info(f"[WORKITEM] {mva} - Work Item created successfully ({len(tiles)} total)")

        # Step 3: Click Done to return to the MVA page.
        # Glass work items stay Open — they are not marked complete here.
        if not click_element(driver, (By.XPATH, "//button[normalize-space()='Done']"), timeout=10):
            log.warning(f"[WORKITEM][WARN] {mva} - 'Done' button not found after work item creation")
            save_failure_screenshot(driver, mva, "done_btn")
            return {"status": "failed", "reason": "done_btn", "mva": mva}

        log.info(f"[FLOW] {mva} - Click Done button — PASSED")
        return {"status": "created", "mva": mva}

    except Exception as e:
        log.error(f"[WORKITEM][ERROR] {mva} - finalize_workitem exception → {e}")
        save_failure_screenshot(driver, mva, "finalize_exception")
        navigate_back_to_home(driver)
        return {"status": "failed", "reason": "exception", "mva": mva}
