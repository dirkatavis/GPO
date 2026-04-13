import time
import os

from selenium.webdriver.common.by import By
from utils.logger import log
from utils.ui_helpers import (click_element, find_element , find_elements)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from flows.opcode_flows import select_opcode    
from flows.mileage_flows import complete_mileage_dialog
from core.complaint_types import ComplaintType, GlassDamageType
from utils.project_paths import ProjectPaths
from config.config_loader import get_config

_DEFAULT_DRIVABILITY = get_config("default_drivability", "Yes")
_GLASS_OPCODE_FALLBACK = get_config("glass_opcode_fallback", "Glass")
_STEP_DELAY = float(get_config("step_delay", 0))


def _step_pause(label: str = "") -> None:
    """Pause between steps when step_delay > 0. Set step_delay in config for debugging."""
    if _STEP_DELAY > 0:
        log.info(f"[STEP] {label} — waiting {_STEP_DELAY}s")
        time.sleep(_STEP_DELAY)



def handle_existing_complaint(driver, mva: str) -> dict:
    """Select an existing complaint tile and advance."""
    log.debug(f"[COMPLAINT] {mva} - Handling existing complaint.")
    if click_element(driver, (By.XPATH, "//button[normalize-space()='Next']")):
        log.info(f"[COMPLAINT] {mva} - Next clicked after selecting existing complaint")
        return {"status": "ok"}

    else:
        log.debug(f"[WORKITEM][WARN] {mva} - could not advance with existing complaint")
        return {"status": "failed", "reason": "existing_complaint_next"}

def handle_new_complaint(driver, mva: str) -> dict:
    """Create and submit a new PM complaint."""
    log.debug(f"[COMPLAINT] {mva} - Handling new complaint.")
    if not (
    click_element(driver, (By.XPATH, "//button[normalize-space()='Add New Complaint']"))
    or click_element(driver, (By.XPATH, "//button[normalize-space()='Create New Complaint']"))
    ):

        log.warning(f"[WORKITEM][WARN] {mva} - Add/Create New Complaint not found")
        return {"status": "failed", "reason": "new_complaint_entry"}

    log.info(f"[WORKITEM] {mva} - Adding new complaint")
    time.sleep(2)

    # Drivability -> configured answer
    log.info(f"[DRIVABLE] {mva} - answering drivability question: {_DEFAULT_DRIVABILITY}")
    if not click_element(driver, (By.XPATH, f"//button[normalize-space()='{_DEFAULT_DRIVABILITY}']")):
        log.warning(f"[WORKITEM][WARN] {mva} - Drivable={_DEFAULT_DRIVABILITY} button not found")
        return {"status": "failed", "reason": "drivable_yes"}
    log.info(f"[COMPLAINT] {mva} - Drivable={_DEFAULT_DRIVABILITY}")


    # Complaint Type -> PM
    if not click_element(driver, (By.XPATH, "//button[normalize-space()='PM']")):
        log.warning(f"[WORKITEM][WARN] {mva} - Complaint type PM not found")
        return {"status": "failed", "reason": "complaint_pm"}
    log.info(f"[COMPLAINT] {mva} - PM complaint selected")


    # Submit
    if not click_element(driver, (By.XPATH, "//button[normalize-space()='Submit Complaint']")):

        log.warning(f"[WORKITEM][WARN] {mva} - Submit Complaint not found")
        return {"status": "failed", "reason": "submit_complaint"}
    log.info(f"[COMPLAINT] {mva} - Submit Complaint clicked")

    # Next -> proceed to Mileage
    if not click_element(driver, (By.XPATH, "//button[normalize-space()='Next']")):
        log.warning(f"[WORKITEM][WARN] {mva} - could not advance after new complaint")
        return {"status": "failed", "reason": "new_complaint_next"}
    log.info(f"[COMPLAINT] {mva} - Next clicked after new complaint")

    return {"status": "ok"}

def handle_complaint(driver, mva: str, found_existing: bool) -> dict:
    """Route complaint handling to existing or new complaint flows."""
    log.debug(f"[COMPLAINT] {mva} - Routing complaint handling. Found existing: {found_existing}")
    if found_existing:
        return handle_existing_complaint(driver, mva)
    else:
        return handle_new_complaint(driver, mva)

def find_dialog(driver):
    locator = (By.CSS_SELECTOR, "div.bp6-dialog, div[class*='dialog']")
    return find_element(driver, locator)

# ----------------------------------------------------------------------------
# AUTHOR:       Dirk Steele <dirk.avis@gmail.com>
# DATE:         2026-04-11
# DESCRIPTION:  Detect complaint tiles containing 'PM' in their text.
#               Used by PM work item handler to find matching existing complaints.
# VERSION:      1.0.0
# NOTES:        Returns only tiles whose text contains 'PM'.
# ----------------------------------------------------------------------------
def detect_pm_complaints(driver, mva: str):
    """Detect complaint tiles containing 'PM' in their text."""
    try:
        time.sleep(3)  # wait for tiles to load
        tiles = driver.find_elements(
            By.XPATH, "//div[contains(@class,'fleet-operations-pwa__complaintItem__')]"
        )
        log.debug(f"[COMPLAINT] {mva} — found {len(tiles)} total complaint tile(s)")

        valid_tiles = [t for t in tiles if "PM" in t.text.strip()]
        log.debug(
            f"[COMPLAINT] {mva} — filtered {len(valid_tiles)} PM-type complaint(s): "
            f"{[t.text for t in valid_tiles]}"
        )

        return valid_tiles
    except Exception as e:
        log.error(f"[COMPLAINT][ERROR] {mva} — complaint detection failed → {e}")
        return []


# ----------------------------------------------------------------------------
# AUTHOR:       Dirk Steele <dirk.avis@gmail.com>
# DATE:         2026-04-11
# DESCRIPTION:  Detect complaint tiles containing glass-related keywords.
#               Used by GlassWorkItemHandler to find matching existing complaints.
#               Keywords are intentionally narrow to avoid false positives
#               (e.g. "replace" is excluded as it matches "brake pad replacement").
# VERSION:      1.0.0
# NOTES:        Returns list of matching tile elements; returns [] on exception.
# ----------------------------------------------------------------------------
def detect_glass_complaints(driver, mva: str = None) -> list:
    """Detect complaint tiles containing glass keywords."""
    glass_keywords = ["glass", "windshield", "crack", "chip", "window"]
    try:
        time.sleep(3)  # wait for tiles to load
        tiles = driver.find_elements(
            By.XPATH, "//div[contains(@class,'fleet-operations-pwa__complaintItem__')]"
        )
        log.debug(f"[COMPLAINT] {mva} — found {len(tiles)} total complaint tile(s)")

        valid_tiles = [
            t for t in tiles
            if any(kw in t.text.lower() for kw in glass_keywords)
        ]
        log.debug(
            f"[COMPLAINT] {mva} — filtered {len(valid_tiles)} glass-type complaint(s): "
            f"{[t.text for t in valid_tiles]}"
        )

        return valid_tiles
    except Exception as e:
        log.error(f"[COMPLAINT][ERROR] {mva} — glass complaint detection failed → {e}")
        return []

def find_pm_tiles(driver, mva: str):
    """Locate complaint tiles of type 'PM' or 'PM Hard Hold - PM'."""
    try:
        tiles = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located(
                (
                    By.XPATH,
                    "//div[contains(@class,'tileContent')][normalize-space(.)='PM - PM' or normalize-space(.)='PM Hard Hold - PM']"
                    "/ancestor::div[contains(@class,'complaintItem')][1]"
                )
            )
        )
        log.info(f"[COMPLAINT] {mva} — found {len(tiles)} PM/Hard Hold PM complaint tile(s)")
        return tiles
    except Exception as e:
        log.info(f"[COMPLAINT] {mva} — no PM complaint tiles found ({e})")
        return []

def associate_existing_complaint(driver, mva: str) -> dict:
    """
    Look for existing glass complaints and associate them.
    Flow: select complaint tile → Next (complaint) → Next (mileage) → Opcode (Glass) → Finalize Work Item.
    """
    log.debug(f"[GLASS][COMPLAINT] {mva} - Associating existing glass complaint.")
    try:
        # Wait for complaint tiles or Add New Complaint button to appear
        time.sleep(3)
        # Find all complaint tiles
        tiles = driver.find_elements(
            By.XPATH, "//div[contains(@class,'fleet-operations-pwa__complaintItem__')]"
        )
        # Look for a glass complaint tile (by text or by image alt)
        glass_tile = None
        for t in tiles:
            # Check text content
            text = t.text.lower()
            if "glass" in text:
                glass_tile = t
                break
            # Check for image alt attribute
            try:
                img = t.find_element(By.XPATH, ".//img[contains(@class,'tileImage')]" )
                alt = img.get_attribute("alt")
                if alt and "glass" in alt.lower():
                    glass_tile = t
                    break
            except Exception:
                pass
        if glass_tile:
            try:
                glass_tile.click()
                log.info(f"[GLASS][COMPLAINT][ASSOCIATED] {mva} - glass complaint selected")
            except Exception as e:
                log.warning(f"[GLASS][COMPLAINT][WARN] {mva} - failed to click glass complaint tile → {e}")
                return {"status": "failed", "reason": "tile_click", "mva": mva}

            # Step 1: Complaint → Next
            if not click_next_in_dialog(driver, timeout=8):
                return {"status": "failed", "reason": "complaint_next", "mva": mva}

            # Step 2: Mileage → Next
            res = complete_mileage_dialog(driver, mva)
            if res.get("status") != "ok":
                return {"status": "failed", "reason": "mileage", "mva": mva}

            # Step 3: Opcode → configured glass fallback
            res = select_opcode(driver, mva, code_text=_GLASS_OPCODE_FALLBACK)
            if res.get("status") != "ok":
                return {"status": "failed", "reason": "opcode", "mva": mva}

            return {"status": "associated", "mva": mva}
        else:
            # No glass complaint found, click Add New Complaint button
            if click_element(driver, (By.XPATH, "//button[.//p[contains(text(),'Add New Complaint')]]")) or \
               click_element(driver, (By.XPATH, "//button[normalize-space()='Add New Complaint']")) or \
               click_element(driver, (By.XPATH, "//button[normalize-space()='Create New Complaint']")):
                log.info(f"[GLASS][COMPLAINT][NEW] {mva} - Add New Complaint clicked (no glass complaint found)")
                return {"status": "skipped_no_complaint", "mva": mva}
            else:
                log.warning(f"[GLASS][COMPLAINT][NEW][WARN] {mva} - could not click Add New Complaint")
                return {"status": "failed", "reason": "add_btn", "mva": mva}
    except Exception as e:
        log.warning(f"[GLASS][COMPLAINT][WARN] {mva} - complaint association failed → {e}")
        return {"status": "failed", "reason": "exception", "mva": mva}

def create_new_complaint(driver, mva: str, complaint_type: str = "glass", drivability: str = "No") -> dict:
    """Create a new complaint when no suitable glass complaint exists."""
    log.debug(f"[GLASS][COMPLAINT] {mva} - Creating new glass complaint.")
    log.info(f"[GLASS][COMPLAINT][NEW] {mva} - creating new glass complaint")

    try:
        # 1. Click Add New Complaint (or Create New Complaint)
        if not (
            click_element(driver, (By.XPATH, "//button[normalize-space()='Add New Complaint']"))
            or click_element(driver, (By.XPATH, "//button[normalize-space()='Create New Complaint']"))
        ):
            log.warning(f"[GLASS][COMPLAINT][NEW][WARN] {mva} - could not click Add/Create New Complaint")
            return {"status": "failed", "reason": "add_btn"}
        log.info(f"[FLOW] {mva} - Click Add New Complaint — PASSED")
        _step_pause("after Add New Complaint")

        # 2. Handle Drivability — glass damage is not drivable ("No")
        if not click_element(driver, (By.XPATH, f"//button[normalize-space()='{drivability}']"), timeout=10, desc=f"Drivability {drivability}"):
            log.warning(f"[GLASS][COMPLAINT][NEW][WARN] {mva} - could not click '{drivability}' in Drivability step")
            return {"status": "failed", "reason": "drivability"}
        log.info(f"[FLOW] {mva} - Click {drivability} Not drivable — PASSED")
        _step_pause("after Drivability")
        time.sleep(1)

        # 3) Select Complaint Type: always click 'Glass Damage' first, then select specific damage type using enums
        # Step 1: Click 'Glass Damage' complaint type (using enum)
        glass_damage_label = ComplaintType.GLASS_DAMAGE.value
        if not click_element(driver, (By.XPATH, f"//button[normalize-space()='{glass_damage_label}']"), timeout=10, desc="Glass Damage complaint type"):
            log.warning(f"[GLASS][COMPLAINT][WARN] {mva} - Complaint type '{glass_damage_label}' not found")
            return {"status": "failed", "reason": "complaint_type", "mva": mva}
        log.info(f"[FLOW] {mva} - Click Glass Damage tile — PASSED")
        _step_pause("after Glass Damage type selected")
        time.sleep(2)

        # Step 2: Select specific glass damage type (using enum)
        # complaint_type may be a string or GlassDamageType; normalize to enum if possible
        damage_type = complaint_type
        if not isinstance(damage_type, GlassDamageType):
            # Create a robust mapping for string to enum conversion
            damage_mapping = {
                # Exact enum values
                "Windshield Crack": GlassDamageType.WINDSHIELD_CRACK,
                "Windshield Chip": GlassDamageType.WINDSHIELD_CHIP,
                "Side/Rear Window Damage": GlassDamageType.SIDE_REAR_WINDOW_DAMAGE,
                "I don't know": GlassDamageType.UNKNOWN,
                
                # Common variations and CSV values
                "REPLACEMENT": GlassDamageType.WINDSHIELD_CRACK,
                "REPAIR": GlassDamageType.WINDSHIELD_CHIP,
                "CRACK": GlassDamageType.WINDSHIELD_CRACK,
                "CHIP": GlassDamageType.WINDSHIELD_CHIP,
                "WINDSHIELD": GlassDamageType.WINDSHIELD_CRACK,
                "FRONT": GlassDamageType.WINDSHIELD_CRACK,
                "SIDE": GlassDamageType.SIDE_REAR_WINDOW_DAMAGE,
                "REAR": GlassDamageType.SIDE_REAR_WINDOW_DAMAGE,
                "UNKNOWN": GlassDamageType.UNKNOWN,
            }
            
            # Try exact match first, then case-insensitive match
            if damage_type in damage_mapping:
                damage_type = damage_mapping[damage_type]
            elif damage_type and damage_type.upper() in damage_mapping:
                damage_type = damage_mapping[damage_type.upper()]
            else:
                # Try direct enum conversion as fallback
                try:
                    damage_type = GlassDamageType(damage_type)
                except ValueError:
                    log.warning(f"[GLASS][COMPLAINT][WARN] {mva} - Unknown damage type '{damage_type}', using default")
                    damage_type = GlassDamageType.UNKNOWN
        damage_label = damage_type.value
        # Use double quotes for XPath to handle apostrophes in text like "I don't know"
        damage_btn_xpath = f'//button[.//h1[text()="{damage_label}"]]'
        if click_element(driver, (By.XPATH, damage_btn_xpath), timeout=10, desc=f"Glass Damage Type: {damage_label}"):
            log.info(f"[FLOW] {mva} - Click {damage_label} — PASSED")
            _step_pause("after damage subtype selected")
            time.sleep(2)  # allow auto-advance to Additional Info screen
        else:
            log.warning(f"[GLASS][COMPLAINT][WARN] {mva} - Glass damage type '{damage_label}' not found")
            # Diagnostic: log page source
            try:
                log.error(driver.page_source)
                # Ensure artifacts directory exists
                artifacts_dir = os.path.join(ProjectPaths.get_project_root(), "artifacts")
                os.makedirs(artifacts_dir, exist_ok=True)
                screenshot_path = os.path.join(artifacts_dir, f"glass_damage_type_error_{mva}.png")
                driver.save_screenshot(screenshot_path)
                log.info(f"Saved screenshot to {screenshot_path}")
            except Exception as se:
                log.error(f"Failed to save screenshot: {se}")
            return {"status": "failed", "reason": "glass_damage_type", "mva": mva}

        # 4) Additional Info screen -> Submit (robust)
        submit_btn_xpath = "//button[contains(., 'Submit Complaint') or contains(., 'Submit')]"
        if click_element(driver, (By.XPATH, submit_btn_xpath), timeout=20, desc="Submit Complaint"):
            log.info(f"[FLOW] {mva} - Click Submit Complaint — PASSED")
            _step_pause("after Submit Complaint")
            time.sleep(2)
        else:
            log.warning(f"[GLASS][COMPLAINT][WARN] {mva} - could not submit Additional Info")
            try:
                artifacts_dir = os.path.join(ProjectPaths.get_project_root(), "artifacts")
                os.makedirs(artifacts_dir, exist_ok=True)
                screenshot_path = os.path.join(artifacts_dir, f"submit_complaint_error_{mva}.png")
                driver.save_screenshot(screenshot_path)
                log.info(f"Saved screenshot to {screenshot_path}")
            except Exception as se:
                log.error(f"Failed to save screenshot: {se}")
            return {"status": "failed", "reason": "submit_info", "mva": mva}

        # After Submit, Compass transitions to the mileage dialog.
        # The caller (work_item_handler) is responsible for clicking Next on the mileage dialog.
        return {"status": "created"}

    except Exception as e:
        log.error(f"[GLASS][COMPLAINT][NEW][ERROR] {mva} - creation failed -> {e}")
        return {"status": "failed", "reason": "exception"}

def click_next_in_dialog(driver, timeout: int = 10) -> bool:
    """
    Click the 'Next' button inside the active dialog.
    Returns True if clicked, False if not found.
    """
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        locator = (By.XPATH, "//button[normalize-space()='Next']")
        log.debug(f"[CLICK] attempting to click {locator} (dialog Next)")

        btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(locator)
        )
        btn.click()

        log.info("[DIALOG] Next button clicked")
        return True

    except Exception as e:
        log.warning(f"[DIALOG][WARN] could not click Next button → {e}")
        return False
