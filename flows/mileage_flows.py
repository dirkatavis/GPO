import time
from utils.logger import log
from selenium.webdriver.common.by import By
from utils.ui_helpers import click_element, send_text


def complete_mileage_dialog(driver, mva: str) -> dict:
    """Click Next on the mileage dialog."""
    log.debug(f"[MILEAGE] {mva} - Completing mileage dialog.")
    try:
        if click_element(driver, (By.XPATH, "//button[normalize-space()='Next']")):
            log.info(f"[MILEAGE] {mva} - Next clicked on mileage dialog")
            return {"status": "ok"}
        else:
            log.info(f"[MILEAGE][FAIL] {mva} - Next button not found")
            return {"status": "failed", "reason": "next_btn"}
    except Exception as e:
        log.error(f"[MILEAGE][ERROR] {mva} - exception -> {e}")
        return {"status": "failed", "reason": "exception"}


def enter_mileage(driver, mva: str, mileage: int) -> dict:
    """Enter the mileage value into the mileage input field."""
    log.debug(f"[MILEAGE] {mva} - Entering mileage: {mileage}")
    log.info(f"[MILEAGE] {mva} - entering mileage: {mileage}")

    try:
        # 1. Find the mileage input field
        # input_field = driver.find_element(By.XPATH, "//input[contains(@class,'mileage-input')]")
        # input_field.clear()
        # input_field.send_keys(str(mileage))

        # 1. Send mileage directly into the input field
        if not send_text(
            driver,
            (By.XPATH, "//input[contains(@class,'mileage-input')]"),
            str(mileage),
        ):
            return {"status": "failed", "reason": "mileage_input"}

        log.info(f"[MILEAGE] {mva} - mileage entered: {mileage}")
        time.sleep(1)

        # 2. Click Next
        if click_element(driver, (By.XPATH, "//button[normalize-space()='Next']")):
            log.info(f"[MILEAGE] {mva} - Next clicked after entering mileage")
            return {"status": "ok"}

        else:
            log.info(
                "[MILEAGE][FAIL] {mva} - Next button not found after entering mileage"
            )
            return {"status": "failed", "reason": "next_btn"}

    except Exception as e:
        log.error(f"[MILEAGE][ERROR] {mva} - exception -> {e}")
        return {"status": "failed", "reason": "exception"}
