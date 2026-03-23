import time

from selenium.webdriver.common.by import By

from utils.logger import log
from utils.ui_helpers import find_element


def select_opcode(driver, mva: str, code_text: str = "PM Gas") -> dict:
    """Select an opcode by visible text from the opcode dialog."""
    log.debug(f"[OPCODE] {mva} - Selecting opcode: {code_text}")
    xpath = (
        "//div[contains(@class,'opCodeItem')]"
        f"[.//div[contains(@class,'opCodeText')][normalize-space()='{code_text}']]"
    )
    log.debug(f" searching for opcode tile -> {xpath}")

    tiles = driver.find_elements(By.XPATH, xpath)
    if not tiles:
        log.warning(f"[WORKITEM][WARN] {mva} - Opcode '{code_text}' not found")
        return {"status": "failed", "reason": "opcode_not_found"}
    else:
        log.debug(f" found {len(tiles)} matching opcode tiles")

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
        f"//div[contains(@class,'opCodeItem')][.//div[contains(@class,'opCodeText')][normalize-space()='{name}']]",
    )
    return find_element(driver, locator)
