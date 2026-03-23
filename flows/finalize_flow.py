import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from utils.logger import log
from utils.ui_helpers import click_element, navigate_back_to_home


def finalize_workitem(driver, mva: str) -> dict:
    """
    Finalize the Work Item creation process.
    Steps:
      1. Click 'Create Work Item'
      2. Wait for Work Item tiles to appear
      3. Complete the Work Item (mark Done)
    """
    log.debug(f"[FINALIZE] {mva} - Finalizing work item.")
    try:
        # Step 1: Click Create Work Item
        if not click_element(driver, (By.XPATH, "//button[normalize-space()='Create Work Item']")):
            log.warning(f"[WORKITEM][WARN] {mva} - 'Create Work Item' button not found")
            return {"status": "failed", "reason": "create_btn", "mva": mva}

        log.info(f"[WORKITEM] {mva} - 'Create Work Item' clicked")
        time.sleep(2)  # allow UI to update

        # Step 2: Verify Work Item exists
        tiles = driver.find_elements(By.XPATH, "//div[contains(@class,'scan-record-header')]")
        if not tiles:
            log.warning(f"[WORKITEM][WARN] {mva} - no Work Item tiles found after creation")
            return {"status": "failed", "reason": "no_tiles", "mva": mva}

        log.info(f"[WORKITEM] {mva} - Work Item created successfully ({len(tiles)} total)")

        # Step 3: Complete the Work Item (lazy import to avoid circular import)
        from flows.work_item_flow import complete_pm_workitem
        res = complete_pm_workitem(driver, mva)
        if res.get("status") != "ok":
            log.warning(f"[WORKITEM][WARN] {mva} - could not complete Work Item")
            return {"status": "failed", "reason": "complete", "mva": mva}

        log.info(f"[WORKITEM] {mva} - Work Item finalized and closed")
        return {"status": "closed", "mva": mva}

    except Exception as e:
        log.error(f"[WORKITEM][ERROR] {mva} - finalize_workitem exception → {e}")
        navigate_back_to_home(driver)
        return {"status": "failed", "reason": "exception", "mva": mva}
