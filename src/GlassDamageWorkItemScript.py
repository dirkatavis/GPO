# --- Imports ---
import sys
import os
import time
import csv
from utils.logger import log
from core.driver_manager import create_driver, quit_driver
from config.config_loader import get_config
from flows.LoginFlow import LoginFlow
from flows.work_item_flow import get_work_items
from flows.complaints_flows import detect_existing_complaints, handle_new_complaint
from flows.opcode_flows import select_opcode
from flows.work_item_handler import WorkItemConfig
from core.complaint_types import ComplaintType, GlassDamageType
from pages.work_item import WorkItem
from pages.mva_input_page import MVAInputPage
from utils.ui_helpers import click_element, navigate_back_to_home
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import selenium.webdriver.common.keys as Keys

# Ensure project root is in sys.path for imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# --- Workflow Step Functions ---
def click_add_work_item(driver):
    """Click the Add Work Item button on the main screen."""
    try:
        log.info("[STEP] Clicking Add Work Item button...")
        # Use the provided class name to locate the button
        button = driver.find_element(By.CLASS_NAME, "fleet-operations-pwa__create-item-button__1k9soug")
        button.click()
        log.info("[STEP] Successfully clicked Add Work Item button.")
        return True
    except Exception as e:
        log.error(f"[STEP][ERROR] Failed to click Add Work Item: {e}")
        return False

def click_add_new_complaint(driver):
    """Click the Add New Complaint button on the complaint screen."""
    try:
        log.info("[STEP] Clicking Add New Complaint button...")
        # Use the provided class name to locate the button
        button = driver.find_element(By.CLASS_NAME, "fleet-operations-pwa__nextButton__5dy90n")
        button.click()
        log.info("[STEP] Successfully clicked Add New Complaint button.")
        return True
    except Exception as e:
        log.error(f"[STEP][ERROR] Failed to click Add New Complaint: {e}")
        return False

def handle_drivability_screen(driver, answer_yes=True):
    """Click Yes/No on the Drivability screen."""
    try:
        log.info(f"[STEP] Clicking {'Yes' if answer_yes else 'No'} on Drivability screen...")
        # Find all drivable option buttons by class name
        buttons = driver.find_elements(By.CLASS_NAME, "fleet-operations-pwa__drivable-option-button__yzn7ir")
        if not buttons or len(buttons) < 2:
            raise Exception("Drivability option buttons not found or insufficient buttons present.")
        # Yes is the first button, No is the second
        target_button = buttons[0] if answer_yes else buttons[1]
        target_button.click()
        log.info(f"[STEP] Successfully clicked {'Yes' if answer_yes else 'No'} on Drivability screen.")
        return True
    except Exception as e:
        log.error(f"[STEP][ERROR] Failed on Drivability screen: {e}")
        return False

def select_complaint_type_glass(driver):
    """Select Glass Damage on Complaint Type screen using enum value.
    """
    complaint_type = ComplaintType.GLASS_DAMAGE.value
    if click_element(driver, (By.XPATH, f"//button[normalize-space()='{complaint_type}']"), timeout=10, desc="Glass complaint type"):
        log.info(f"[STEP] Selected complaint type: {complaint_type}")
        return True

    if click_element(driver, (By.XPATH, f"//button[.//h1[text()=\"{complaint_type}\"]]"), timeout=10, desc="Glass complaint type"):
        log.info(f"[STEP] Selected complaint type: {complaint_type}")
        return True

    log.error(f"[STEP][ERROR] Failed to select complaint type: {complaint_type}")
    return False

def select_glass_damage_type(driver, damage_type):
    """Select the specific glass damage type using enum value or string mapping.
    """
    # If damage_type is already an enum value, use it directly
    # If it's a string, try to map it to an enum
    if damage_type in [gdt.value for gdt in GlassDamageType]:
        glass_type_label = damage_type
    else:
        # Fallback mapping for legacy strings
        damage_mapping = {
            'REPLACEMENT': GlassDamageType.WINDSHIELD_CRACK.value,
            'REPAIR': GlassDamageType.WINDSHIELD_CHIP.value,
            'WINDSHIELD': GlassDamageType.WINDSHIELD_CRACK.value,
            'FRONT': GlassDamageType.WINDSHIELD_CRACK.value,
        }
        glass_type_label = damage_mapping.get(damage_type.upper(), GlassDamageType.UNKNOWN.value)
    
    return select_glass_damage_option(driver, option_text=glass_type_label)

def submit_complaint(driver):
    """Click Submit Complaint button.
    """
    return click_submit_complaint(driver)

def click_next_on_mileage(driver):
    """Click Next on the Mileage screen.
    """
    return click_mileage_next(driver)

def select_opcode_glass(driver):
    """Select 'Glass Repair/Replace' on OpsCode screen.
    """
    primary_opcode = get_config("glass_opcode_primary", "Glass Repair/Replace")
    fallback_opcode = get_config("glass_opcode_fallback", "Glass")

    result = select_opcode(driver, "N/A", code_text=primary_opcode)
    if result.get("status") == "ok":
        return True

    fallback = select_opcode(driver, "N/A", code_text=fallback_opcode)
    return fallback.get("status") == "ok"

def click_create_work_item(driver):
    """Click Create Work Item button on OpsCode screen."""
    try:
        log.info("[STEP] Clicking Create Work Item button...")
        return True
    except Exception as e:
        log.error(f"[STEP][ERROR] Failed to click Create Work Item: {e}")
        return False

def click_done_on_work_item(driver):
    """Click Done button on Work Item screen."""
    try:
        log.info("[STEP] Clicking Done button on Work Item screen...")
        return True
    except Exception as e:
        log.error(f"[STEP][ERROR] Failed to click Done: {e}")
        return False

# --- Helper Functions for MVA Input Operations ---

def find_mva_input_field(mva_input_page, mva, attempt, max_attempts):
    """Find and validate the MVA input field with retries.
    
    Returns:
        WebElement: The input field if found and valid, None otherwise
    """
    input_field = mva_input_page.find_input()
    if not (input_field and input_field.is_enabled() and input_field.is_displayed()):
        try:
            input_field = WebDriverWait(mva_input_page.driver, 5, poll_frequency=0.25).until(
                lambda d: (
                    (f := mva_input_page.find_input()) and f.is_enabled() and f.is_displayed() and f
                )
            )
        except TimeoutException:
            input_field = None
    
    if not input_field:
        log.error(f"[MVA][FATAL] Could not find MVA input field for {mva}. Attempt {attempt}/{max_attempts}.")
        if attempt == max_attempts:
            log.error(f"[MVA][FATAL] Skipping {mva} after {max_attempts} attempts.")
        return None
    
    return input_field

def clear_and_enter_mva(input_field, mva):
    """Clear the input field thoroughly and enter the new MVA value.
    
    Args:
        input_field: WebElement for the MVA input field
        mva: String value to enter
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Clear the field using multiple methods for robustness
        for _ in range(3):
            input_field.send_keys(Keys.Keys.CONTROL + 'a')
            input_field.send_keys(Keys.Keys.DELETE)
            input_field.clear()
            time.sleep(0.2)
        
        # Wait up to 1s (4 x 250ms) for the field to be empty
        for _ in range(4):
            if input_field.get_attribute("value") == "":
                break
            time.sleep(0.25)
        else:
            log.warning(f"[MVA_INPUT] Field not empty after clearing attempts!")
        
        # Wait up to 3 seconds for the field to be empty
        for _ in range(15):
            if input_field.get_attribute("value") == "":
                break
            time.sleep(0.2)
        
        if input_field.get_attribute("value") != "":
            log.warning(f"[MVA_INPUT] Field not fully cleared before entering new MVA!")
            return False
        else:
            log.info(f"[MVA_INPUT] Field cleared before entering new MVA.")
        
        # Enter the new MVA value
        input_field.send_keys(mva)
        log.info(f"[MVA_INPUT] Entered MVA: {mva}")
        return True
        
    except Exception as e:
        log.error(f"[MVA_INPUT] Error during clear and enter operation: {e}")
        return False

# --- Main Script Configuration ---

MVA_CSV = "data/GlassDamageWorkItemScript.csv"




def read_csv_rows(csv_path):
    """Read rows from CSV, skipping empty and comment rows."""
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        return [row for row in reader if row and row.get('MVA') and not row['MVA'].strip().startswith('#')]

def create_work_item_config(row):
    """Create WorkItemConfig from a CSV row with proper enum mapping."""
    mva = row['MVA'].strip()
    
    # Map CSV damage type to GlassDamageType enum
    damage_type_str = row.get('DamageType', '').strip().upper() if row.get('DamageType') else ''
    location_str = row.get('Location', '').strip().upper() if row.get('Location') else ''
    
    # Map common CSV values to enum values
    glass_damage_type = None
    if 'REPLACEMENT' in damage_type_str and ('FRONT' in location_str or 'WINDSHIELD' in location_str):
        glass_damage_type = GlassDamageType.WINDSHIELD_CRACK  # Default to crack for windshield replacement
    elif 'CHIP' in damage_type_str:
        glass_damage_type = GlassDamageType.WINDSHIELD_CHIP
    elif 'REPAIR' in damage_type_str and ('FRONT' in location_str or 'WINDSHIELD' in location_str):
        glass_damage_type = GlassDamageType.WINDSHIELD_CHIP  # Repairs are typically for chips
    elif 'SIDE' in location_str or 'REAR' in location_str:
        glass_damage_type = GlassDamageType.SIDE_REAR_WINDOW_DAMAGE
    else:
        glass_damage_type = GlassDamageType.WINDSHIELD_CRACK  # Default to windshield crack instead of unknown
    
    return WorkItemConfig(
        mva=mva,
        damage_type=glass_damage_type.value,  # Store enum value as string
        location=location_str
    )

def log_work_item_config(config):
    """Log details of a WorkItemConfig."""
    log.info(f"[CSV] Loading work item: {config.mva} (DamageType: {config.damage_type}, Location: {config.location})")

def select_glass_damage_option(driver, option_text="Glass Damage"):
    """
    Selects a glass damage option by visible text (e.g., 'Windshield Crack', 'Windshield Chip', 'Side/Rear Window Damage').
    Args:
        driver: Selenium WebDriver instance
        option_text: The visible text of the glass damage option to select
    Returns:
        True if the option was found and clicked, False otherwise
    """
    try:
        log.info(f"[STEP] Selecting glass damage option: '{option_text}' ...")
        # Find all damage option buttons by class name
        buttons = driver.find_elements(By.CLASS_NAME, "fleet-operations-pwa__damage-option-button__yzn7ir")
        if not buttons:
            raise Exception("No damage option buttons found.")
        for button in buttons:
            try:
                # The button text is inside a <h1> tag within the button
                h1 = button.find_element(By.TAG_NAME, "h1")
                text = h1.text.strip()
                if text == option_text:
                    button.click()
                    log.info(f"[STEP] Successfully clicked '{option_text}' option.")
                    return True
            except Exception:
                continue
        raise Exception(f"'{option_text}' option not found among buttons.")
    except Exception as e:
        log.error(f"[STEP][ERROR] Failed to select glass damage option '{option_text}': {e}")
        return False

def click_submit_complaint(driver):
    """
    Clicks the 'Submit Complaint' button on the page.
    Args:
        driver: Selenium WebDriver instance
    Returns:
        True if the button was found and clicked, False otherwise
    """
    try:
        log.info("[STEP] Clicking 'Submit Complaint' button ...")
        # Find all submit buttons by class name
        buttons = driver.find_elements(By.CLASS_NAME, "fleet-operations-pwa__submit-button__yzn7ir")
        if not buttons:
            raise Exception("No submit buttons found.")
        for button in buttons:
            try:
                # The button text is inside a <span> tag within the button
                span = button.find_element(By.TAG_NAME, "span")
                text = span.text.strip()
                if text == "Submit Complaint":
                    button.click()
                    log.info("[STEP] Successfully clicked 'Submit Complaint' button.")
                    return True
            except Exception:
                continue
        raise Exception("'Submit Complaint' button not found among buttons.")
    except Exception as e:
        log.error(f"[STEP][ERROR] Failed to click 'Submit Complaint' button: {e}")
        return False

def click_mileage_next(driver):
    """
    Clicks the 'Next' button on the Mileage screen.
    Args:
        driver: Selenium WebDriver instance
    Returns:
        True if the button was found and clicked, False otherwise
    """
    try:
        log.info("[STEP] Clicking 'Next' button on Mileage screen ...")
        # Find all next buttons by class name
        buttons = driver.find_elements(By.CLASS_NAME, "fleet-operations-pwa__nextButton__5dy90n")
        if not buttons:
            raise Exception("No 'Next' buttons found on Mileage screen.")
        for button in buttons:
            try:
                # The button text is inside a <p> tag within a <span> inside the button
                span = button.find_element(By.TAG_NAME, "span")
                p = span.find_element(By.TAG_NAME, "p")
                text = p.text.strip()
                if text == "Next":
                    button.click()
                    log.info("[STEP] Successfully clicked 'Next' button on Mileage screen.")
                    return True
            except Exception:
                continue
        raise Exception("'Next' button not found among buttons on Mileage screen.")
    except Exception as e:
        log.error(f"[STEP][ERROR] Failed to click 'Next' button on Mileage screen: {e}")
        return False

def get_work_item_configs(csv_path):
    """Read, filter, create, and log WorkItemConfig objects from CSV."""
    rows = read_csv_rows(csv_path)
    configs = []
    for row in rows:
        config = create_work_item_config(row)
        configs.append(config)
        log_work_item_config(config)
    return configs


# ----------------------------------------------------------------------------
# AUTHOR:       Dirk Steele <dirk.avis@mail.com>
# DATE:         2026-01-12
# DESCRIPTION:  Read glass work items from CSV and return WorkItemConfig objects.
#               Skips comments and empty rows, logs each loaded config.
# VERSION:      1.0.0
# NOTES:        Expects columns: MVA, DamageType, Location.
# ----------------------------------------------------------------------------

def main():
    username = os.getenv("GLASS_LOGIN_USERNAME") or get_config("username")
    password = os.getenv("GLASS_LOGIN_PASSWORD") or get_config("password")
    login_id = os.getenv("GLASS_LOGIN_ID") or get_config("login_id")
    driver = create_driver()
    mva_input_page = MVAInputPage(driver)
    login_flow = LoginFlow(driver)
    login_result = login_flow.login_handler(username, password, login_id)
    if login_result.get("status") != "ok":
        log.error(f"[LOGIN] Failed to initialize session → {login_result}")
        return

    mva_list = get_work_item_configs(MVA_CSV)
    for work_item_config in mva_list:
        # after finding the first work item type sought we can break out of the loop
        mva = work_item_config.mva
        mva_header = f"\n{'*'*32}\nMVA {mva}\n{'*'*32}"
        log.info(mva_header)
        log.info(f"[MVA] Reviewing {mva} (Type: {work_item_config.damage_type}, Location: {work_item_config.location})")
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                # --- Robust MVA input logic using helper functions ---
                input_field = find_mva_input_field(mva_input_page, mva, attempt, max_attempts)
                if not input_field:
                    if attempt < max_attempts:
                        time.sleep(2)
                    continue  # Skip to next attempt or exit loop
                    
                # Clear field and enter new MVA
                if not clear_and_enter_mva(input_field, mva):
                    log.error(f"[MVA_INPUT] Failed to clear and enter MVA {mva}")
                    if attempt < max_attempts:
                        time.sleep(2)
                    continue  # Skip to next attempt

                # --- End robust MVA input logic ---

                # Wait for vehicle properties container to appear (indicates valid MVA)
                try:
                    log.info(f"[MVA_VALIDATION] Waiting for vehicle properties to load for {mva}...")
                    WebDriverWait(driver, 30, poll_frequency=1.0).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.fleet-operations-pwa__vehicle-properties-container__1ad7kyc"))
                    )
                    log.info(f"[MVA_VALIDATION] Vehicle properties loaded successfully for {mva}")
                except TimeoutException:
                    log.warning(f"[MVA_VALIDATION] Vehicle properties not found for {mva} - MVA may be invalid or non-existent")
                    break  # Skip to next MVA

                # Dynamic wait for work items to load/update after vehicle properties appear  
                # Poll every 0.5 seconds with 3 second timeout for responsive timing
                try:
                    log.info(f"[MVA_VALIDATION] Waiting for work items to load for {mva}...")
                    WebDriverWait(driver, 3.0, poll_frequency=0.5).until(
                        lambda d: len(d.find_elements(By.CSS_SELECTOR, ".work-item, [class*='work-item'], [class*='workitem']")) > 0
                    )
                    log.info(f"[MVA_VALIDATION] Work items loaded successfully for {mva}")
                except TimeoutException:
                    log.info(f"[MVA_VALIDATION] No work items found after 3 seconds for {mva} - assuming none exist")
                
                # Brief pause to ensure UI is stable after work item detection
                time.sleep(0.2)
                work_items = get_work_items(driver, mva)
                # Only proceed if there are no existing glass work items
                glass_found = False
                glass_complaint_label = ComplaintType.GLASS_DAMAGE.value.lower()  # "glass damage"
                for wi in work_items:
                    # Debug: Log the actual text and its properties
                    log.info(f"[DEBUG] Work item text: '{wi.text}'")
                    log.info(f"[DEBUG] Text length: {len(wi.text)}")
                    log.info(f"[DEBUG] Text repr: {repr(wi.text)}")
                    log.info(f"[DEBUG] Lowercased: '{wi.text.lower()}'")
                    log.info(f"[DEBUG] Contains '{glass_complaint_label}': {glass_complaint_label in wi.text.lower()}")
                    if glass_complaint_label in wi.text.lower():
                        glass_found = True
                        log.info(f"[GLASS] Glass damage work item already exists for {mva}")
                        break
                if glass_found:
                    break  # No need to create a new work item, exit retry loop

                # If there are work items but none are glass, or if there are no work items at all, create new glass work item
                
                from flows.work_item_flow import create_work_item_with_handler
                result = create_work_item_with_handler(driver, work_item_config, handler_type="GLASS")
                if result.get("status") == "created":
                    log.info(f"[GLASS] Glass damage work item created for {mva}")
                else:
                    log.error(f"[GLASS][ERROR] Failed to create glass work item for {mva}: {result}")
                
                # Navigate back to home page for next MVA
                try:
                    navigate_back_to_home(driver)
                    log.info(f"[NAVIGATION] Successfully navigated back to home page after processing {mva}")
                except Exception as nav_error:
                    log.error(f"[NAVIGATION][ERROR] Failed to navigate back to home page: {nav_error}")
                
                break  # Success or failure, exit retry loop
            except Exception as e:
                log.error(f"[ERROR] Exception for {mva} (attempt {attempt}/{max_attempts}): {e}")
                if attempt == max_attempts:
                    log.error(f"[MVA][FATAL] Skipping {mva} after {max_attempts} attempts due to repeated errors.")
                else:
                    time.sleep(2)
        time.sleep(2)

    # Ensure the browser is closed after all automation is finished
    try:
        quit_driver()
        log.info("[SESSION] Browser closed.")
    except Exception as e:
        log.warning(f"[SESSION] Failed to close browser: {e}")

# ----------------------------------------------------------------------------
# AUTHOR:       Dirk Steele <dirk.avis@mail.com>
# DATE:         2026-01-12
# DESCRIPTION:  Main script logic. Logs in, iterates MVAs, checks for glass work items,
#               and creates new ones if needed. Handles robust MVA input and error handling.
# VERSION:      1.0.0
# NOTES:        Uses robust field clearing and retry logic for reliability.
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
