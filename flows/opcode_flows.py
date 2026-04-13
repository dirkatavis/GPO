import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils.logger import log
from utils.ui_helpers import find_element
from config.config_loader import get_config

_OPCODE_DIALOG_READY_XPATH = "//div[contains(@class,'opCodeText')]"


def select_opcode(driver, mva: str, code_text: str = None) -> dict:
    """Select an opcode by visible text from the opcode dialog."""
    if code_text is None:
        code_text = get_config("default_opcode", "PM Gas")
    log.debug(f"[OPCODE] {mva} - Selecting opcode: {code_text}")

    # Wait for the opcode dialog to render at least one tile before searching.
    # Without this the search fires ~150ms after the mileage Next click and
    # the dialog hasn't painted yet.
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, _OPCODE_DIALOG_READY_XPATH))
        )
    except Exception:
        log.warning(f"[WORKITEM][WARN] {mva} - Opcode dialog did not appear within 15s")
        return {"status": "failed", "reason": "opcode_not_found"}

    # Match directly on the text div — avoids dependency on the parent container's
    # hash-suffixed class name (opCodeItem__<hash> varies per Compass build).
    # Use contains() rather than exact normalize-space() equality because icon-font
    # glyphs in sibling/child elements can bleed into the element's text value.
    xpath = f"//div[contains(@class,'opCodeText')][contains(normalize-space(),'{code_text}')]"
    log.debug(f" searching for opcode text div -> {xpath}")

    tiles = driver.find_elements(By.XPATH, xpath)
    if not tiles:
        # Dump all opCodeText divs so we can see what IS available
        all_texts = driver.find_elements(By.XPATH, "//div[contains(@class,'opCodeText')]")
        found_texts = []
        for item in all_texts:
            try:
                found_texts.append(repr(item.text.strip()))
            except Exception:
                found_texts.append("<unreadable>")
        log.warning(
            f"[WORKITEM][WARN] {mva} - Opcode '{code_text}' not found. "
            f"Found {len(all_texts)} opCodeText div(s): {', '.join(found_texts) or 'none'}"
        )
        return {"status": "failed", "reason": "opcode_not_found"}
    else:
        log.debug(f" found {len(tiles)} matching opcode text div(s)")

    tile = tiles[0]
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", tile)
    time.sleep(1)
    tile.click()
    log.info(f"[COMPLAINT] {mva} - Opcode '{code_text}' selected")
    return {"status": "ok"}


def find_opcode_tile(driver, name: str):
    log.debug(f"[OPCODE] Finding opcode tile: {name}")
    locator = (
        By.XPATH,
        f"//div[contains(@class,'opCodeText')][contains(normalize-space(),'{name}')]",
    )
    return find_element(driver, locator)
