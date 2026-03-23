"""Flows for creating, processing, and handling Compass Work Items."""
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from flows.complaints_flows import associate_existing_complaint
from flows.finalize_flow import finalize_workitem
from utils.logger import log
from utils.ui_helpers import click_element, safe_wait

def get_work_items(driver, mva: str):
    """Collect all open glass work items for the given MVA."""
    log.debug(f"[WORKITEM] {mva} - Getting work items.")
    log.info(f"[WORKITEM] {mva} - pausing to let Work Items render...")
    #time.sleep(9)  # wait for UI to render
    # Better: wait for the work items container to be present
    safe_wait(driver, 15, EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'fleet-operations-pwa__scan-record__')]")), desc="Work Items container")
    try:
        # Check for 'No work items yet...' message
        no_items = driver.find_elements(By.XPATH, "//div[contains(@class, 'bp6-entity-title-title') and contains(text(), 'No work items yet')]")
        if no_items:
            log.info(f"[WORKITEMS] {mva} - No work items yet...")
            return []

        # Get all open work item tiles (not just glass)
        tiles = driver.find_elements(
            By.XPATH,
            "//div[contains(@class, 'fleet-operations-pwa__scan-record__') and .//div[contains(@class, 'fleet-operations-pwa__scan-record-header-title-right__') and normalize-space()='Open']]"
        )
        log.info(f"[WORKITEMS] {mva} - collected {len(tiles)} open work item(s)")
        for t in tiles:
            log.debug(f"[DBG] {mva} - tile text = {t.text!r}")
        return tiles
    except NoSuchElementException as e:
        log.warning(f"[WORKITEM][WARN] {mva} - could not collect work items -> {e}")
        return []





def create_new_workitem(driver, mva: str):
    """Create a new Work Item for the given MVA."""
    log.debug(f"[WORKITEM] {mva} - Creating new work item.")
    log.info(f"[WORKITEM] {mva} - starting CREATE NEW WORK ITEM workflow")

    # Step 1: Click Add Work Item
    try:
        time.sleep(5)  # wait for button to appear
        # Increase timeout to 30 seconds for clicking Add Work Item
        if not click_element(driver, (By.XPATH, "//button[normalize-space()='Add Work Item']"), timeout=30, desc="Add Work Item button"):
            log.warning(f"[WORKITEM][WARN] {mva} - add_btn not found")
            return {"status": "failed", "reason": "add_btn", "mva": mva}
        log.info(f"[WORKITEM] {mva} - Add Work Item clicked")
        time.sleep(5)

    except NoSuchElementException:
        log.warning(f"[WORKITEM][WARN] {mva} - add_btn failed -> {e}")
        return {"status": "failed", "reason": "add_btn", "mva": mva}

    # Step 2: Complaint handling (glass-specific)
    from flows.complaints_flows import associate_existing_complaint, create_new_complaint
    try:
        res = associate_existing_complaint(driver, mva)
        if res["status"] == "associated":
            log.info(f"[GLASS][ASSOCIATED] {mva} - existing glass complaint linked to Work Item")
        else:
            log.info(f"[GLASS][INFO] {mva} - no existing glass complaint found, creating new complaint...")
            # FOR GLASS: here is where the user would answer Is vehicle driverable? -> Yes/No
            # This already  works for PM so we need to be careful not to break that flow.
            # For now, we will assume "Yes" for driveable.
            res = create_new_complaint(driver, mva, complaint_type=None)
            if res["status"] != "created":
                log.error(f"[GLASS][ERROR] {mva} - failed to create glass complaint: {res}")
                return res
    except NoSuchElementException as e:
        log.warning(f"[WORKITEM][WARN] {mva} - complaint handling failed -> {e}")
        return {"status": "failed", "reason": "complaint_handling", "mva": mva}

    # Step 3: Finalize Work Item (call will be injected here in refactor later)
    log.warning(f"[WORKITEM][WARN] {mva} - finalize step skipped (refactor placeholder)")
    return {"status": "created", "mva": mva}


def create_work_item_with_handler(driver, config, handler_type: str = "GLASS"):
    """
    Create a work item using the handler pattern.
    
    Args:
        driver: WebDriver instance
        config: WorkItemConfig object with MVA and work item specific data
        handler_type: Type of work item handler to use (GLASS, PM, etc.)
    Returns:
        Dict with status and details of work item creation
    """
    from flows.work_item_handler import create_work_item_handler
    
    try:
        # Create appropriate handler
        handler = create_work_item_handler(handler_type, driver)
        # Execute work item creation using handler
        # 
        return handler.create_work_item(config)
    except Exception as e:
        log.error(f"[WORKITEM][ERROR] {config.mva} - Handler execution failed: {e}")
        return {"status": "failed", "reason": "handler_error", "mva": config.mva, "error": str(e)}


def get_lighthouse_status(driver, mva: str) -> str | None:
    """
    Return the Lighthouse status string for the given MVA, or None.
    Statuses: 'Rentable', 'PM', 'PM Hard Hold', etc.
    """
    log.debug(f"[LIGHTHOUSE] {mva} - getting Lighthouse status")
    try:
        status_el = driver.find_element(
            By.XPATH,
            "//div[contains(@class, 'fleet-operations-pwa__vehicle-property__') and ./div[contains(., 'Lighthouse')]]//div[contains(@class, 'fleet-operations-pwa__vehicle-property-value__')]",
        )
        status = status_el.text.strip()
        log.info(f"[LIGHTHOUSE] {mva} - found status: {status}")
        return status
    except NoSuchElementException:
        log.info(f"[LIGHTHOUSE] {mva} - status field not found")
        return None
    except Exception as e:
        log.error(f"[LIGHTHOUSE] {mva} - error getting status: {e}")
        return None


def handle_pm_workitems(driver, mva: str) -> dict:
    """
    Handle PM Work Items for a given MVA:
      1. If an open PM Work Item exists, complete it.
      2. Otherwise, start a new Work Item.
         - Try to associate an existing complaint.
         - If none, skip and return control to the test loop.
    """
    log.info(f"[WORKITEM] {mva} - handling PM work items")

    # Get Lighthouse status
    lighthouse_status = get_lighthouse_status(driver, mva)

    # Case 1: Rentable
    if lighthouse_status and "rentable" in lighthouse_status.lower():
        log.info(f"[LIGHTHOUSE] {mva} - Status is 'Rentable', skipping MVA.")
        return {"status": "skipped_lighthouse_rentable", "mva": mva}

    # Case 2: Existing open PM work items
    items = get_work_items(driver, mva)
    if items:
        log.info(f"[WORKITEM] {mva} - open PM Work Item found, completing it")
        from flows.work_item_flow import complete_pm_workitem
        return complete_pm_workitem(driver, mva)

    # Case 3: No open work items.
    # Click "Add Work Item" to proceed to the complaint association screen.
    if not click_element(driver, (By.XPATH, "//button[normalize-space()='Add Work Item']"),
                     desc="Add Work Item", timeout=8):
        log.warning(f"[WORKITEM][WARN] {mva} - could not click Add Work Item")
        return {"status": "failed", "reason": "add_btn", "mva": mva}
    
    log.info(f"[WORKITEM] {mva} - Add Work Item clicked")

    # Now, on the complaints screen, check for existing complaints.
    from flows.complaints_flows import associate_existing_complaint
    res = associate_existing_complaint(driver, mva)

    # Sub-case 3a: A complaint was successfully associated.
    if res.get("status") == "associated":
        from flows.finalize_flow import finalize_workitem
        return finalize_workitem(driver, mva)

    # Sub-case 3b: No existing PM complaint was found.
    elif res.get("status") == "skipped_no_complaint":
        # NEW: Check for the special CDK case.
        if lighthouse_status and "pm" in lighthouse_status.lower():
            log.info(f"[WORKITEM] {mva} - ***PM for MVA {mva} must be closed out in CDK***")
            from utils.ui_helpers import navigate_back_to_home
            navigate_back_to_home(driver)
            return {"status": "skipped_cdk_pm", "mva": mva}
        else:
            # Original behavior: just navigate back if no complaint and not a PM case.
            log.info(f"[WORKITEM] {mva} - navigating back home after skip")
            from utils.ui_helpers import navigate_back_to_home
            navigate_back_to_home(driver)
            return res
    
    # Sub-case 3c: The complaint association process failed.
    return res







def process_workitem(driver, mva: str):
    """Main entry point for processing a Work Item for the given MVA."""
    log.info(f"[WORKITEM] {mva} - starting process")

    # Step 1: Gather existing Work Items
    tiles = get_work_items(driver, mva)
    total = len(tiles)
    log.info(f"[WORKITEM] {mva} - {total} total work items found")

    if total == 0:
        log.info(f"[WORKITEM][SKIP] {mva} - no PM work items found")
        return {"status": "skipped", "reason": "no_pm_workitems", "mva": mva}

    # Step 2: Handle existing Open PM Work Items
    res = complete_pm_workitem(driver, mva, timeout=8)
    return res



def open_pm_workitem_card(driver, mva: str, timeout: int = 8) -> dict:
    """Find and open the first Open PM Work Item card."""
    try:
        # Step 1: Find the parent div that contains both the title and the 'PM' complaint
        log.info(f"[WORKITEM] {mva} - Searching for the PM work item card...")
        
        parent_card = driver.find_element(
            By.XPATH,
            "//div[contains(@class, 'fleet-operations-pwa__scan-record__') and ./div[contains(@class, 'fleet-operations-pwa__scan-record-header__')] and ./div[contains(@class, 'fleet-operations-pwa__scan-record-row-2__') and contains(., 'PM')]]"
        )
        
        log.info(f"[WORKITEM] {mva} - Found the parent card.")
        
        # Step 2: Find the title bar element within the parent card
        log.info(f"[WORKITEM] {mva} - Searching for the title bar within the found card...")
        
        title_bar = parent_card.find_element(
            By.XPATH,
            "./div[contains(@class, 'fleet-operations-pwa__scan-record-header__')]"
        )
        
        log.info(f"[WORKITEM] {mva} - Found the title bar.")
        
        # Step 3: Click the title bar
        title_bar.click()
        
        log.info(f"[WORKITEM] {mva} - Open PM Work Item card clicked")
        
        return {"status": "ok", "reason": "card_opened", "mva": mva}
    
    except Exception as e:
        log.warning(f"[WORKITEM][WARN] {mva} - could not open Open PM Work Item card -> {e}")
        return {"status": "failed", "reason": "open_pm_card", "mva": mva}
    
    
    


def complete_work_item_dialog(driver, note: str = "Done", timeout: int = 10, observe: int = 0) -> dict:
    """Fill the correction dialog with note and click 'Complete Work Item'."""
    try:
        # 1) Wait for visible dialog root
        dialog = safe_wait(
            driver,
            timeout,
            EC.visibility_of_element_located((By.CSS_SELECTOR, "div.bp6-dialog")),
            desc="Work Item dialog"
        )

        log.info("[DIALOG] Correction dialog opened")

        # 2) Find textarea (scoped to dialog)
        textarea = safe_wait(
            driver,
            timeout,
            EC.visibility_of_element_located((By.CSS_SELECTOR, "textarea.bp6-text-area")),
            desc="Correction textarea"
        )
        time.sleep(5)
        textarea.click()        
        time.sleep(5)
        textarea.clear()
        time.sleep(5)
        textarea.send_keys(note)
        time.sleep(5)
        log.info(f"[DIALOG] Entered note text: {note!r}")
        time.sleep(5)

        # 3) Click 'Complete Work Item'
        complete_btn = safe_wait(
            driver,
            timeout,
            EC.element_to_be_clickable((By.XPATH, "//div[contains(@class,'bp6-dialog')]//button[normalize-space()='Complete Work Item']")),
            desc="Complete Work Item button"
        )
        time.sleep(5)


        complete_btn.click()
        log.info("[DIALOG] 'Complete Work Item' button clicked")
    

        # 4) Wait for dialog to close
        safe_wait(driver ,timeout, EC.invisibility_of_element(dialog), desc="Dialog to close")    

        log.info("[DIALOG] Correction dialog closed")

        # The issue might be that closing the UI short after clicking the button 
        # doesn't give enough time for the backend to process the completion.
        # Adding a longer wait here to ensure the process completes before proceeding.
        time.sleep(10)

        return {"status": "ok"}
    except Exception as e:
        log.error(f"[DIALOG][ERROR] complete_work_item_dialog -> {e}")
        return {"status": "failed", "reason": "dialog_exception"}



def mark_complete_pm_workitem(driver, mva: str, note: str = "Done", timeout: int = 8) -> dict:
    """Click 'Mark Complete', then complete the dialog with the given note."""
    if not click_element(driver, (By.XPATH, "//button[normalize-space()='Mark Complete']")):
        return {"status": "failed", "reason": "mark_complete_button", "mva": mva}

    time.sleep(0.2)
    res = complete_work_item_dialog(driver, note=note, timeout=max(10, timeout), observe=1)
    log.info(f"[MARKCOMPLETE] complete_work_item_dialog -> {res}")

    if res and res.get("status") == "ok":
        return {"status": "ok", "reason": "dialog_complete", "mva": mva}
    else:
        return {"status": "failed", "reason": res.get("reason", "dialog_failed"), "mva": mva}




def complete_pm_workitem(driver, mva: str, timeout: int = 8) -> dict:
    """Open the PM Work Item card and mark it complete with note='Done'."""
    time.sleep(5)  # wait for UI to stabilize
    res = open_pm_workitem_card(driver, mva, timeout=timeout)
    if res.get("status") != "ok":
        return res  # pass through failure dict
    time.sleep(5)  # wait for card to open
    res = mark_complete_pm_workitem(driver, mva, note="Done", timeout=timeout)
    time.sleep(5)  # wait for completion to process
    if res.get("status") == "ok":
        return {"status": "ok", "reason": "completed_open_pm", "mva": mva}
    else:
        return {"status": "failed", "reason": res.get("reason", "mark_complete"), "mva": mva}