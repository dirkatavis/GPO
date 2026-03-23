import json
import time
import pytest
import os
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys  # ✅ add this import at the top
from selenium.webdriver.support import expected_conditions as EC


from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


from core.navigator import Navigator
from utils.logger import log
from utils.ui_helpers import click_element, safe_wait, send_text


class LoginPage:
    def __init__(self, driver):
        self.driver = driver

        # Hardcoded config path
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        config_path = os.path.join(project_root, "config", "config.json")
        with open(config_path, "r") as f:
            config = json.load(f)
            self.delay_seconds = config.get("delay_seconds", 4)

    def is_logged_in(self):
        """Check if Compass Mobile session is already authenticated."""
        
        log.info(f"[DEBUG] inside is_logged_in")
        elems = self.driver.find_elements(By.XPATH, "//span[contains(text(),'Compass Mobile')]")
        return len(elems) > 0

    def ensure_logged_in(self, username: str, password: str, login_id: str):
        # Always navigate first
        Navigator(self.driver).go_to(
            "https://avisbudget.palantirfoundry.com/multipass/login", label="Login page"
        )

        # Check if already on the workspace page after redirection
        if "/workspace/module/view/" in self.driver.current_url:
            log.info("[LOGIN] Already on workspace page after redirection. Considering logged in.")
            return {"status": "ok"}

        # Handle automatic login redirection
        if "/multipass/automatic-login" in self.driver.current_url:
            log.info("[LOGIN] Automatic login page detected. Assuming login will succeed.")
            return {"status": "ok"}

        # Check if already on the workspace page after redirection
        if "/workspace/module/view/" in self.driver.current_url:
            log.info("[LOGIN] Already on workspace page after redirection. Considering logged in.")
            return {"status": "ok"}

        # If not on workspace, check if login form is present and perform login
        # We need to check for the email field to determine if we are on the login page
        email_field_present = False
        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.NAME, "loginfmt"))
            )
            email_field_present = True
        except TimeoutException:
            pass

        if email_field_present:
            log.info("[LOGIN] Login form detected. Performing login()...")
            return self.login(username, password, login_id)
        else:
            log.error("[LOGIN] Neither workspace nor login form detected after navigation. Unexpected state.")
            return {"status": "failed", "reason": "unexpected_page_state"}

    def enter_wwid(self, login_id: str):
        """Actually type and submit the WWID once."""
        try:
            safe_wait(
                self.driver,
                10,
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input[class*='fleet-operations-pwa__text-input__']")
                ),
                desc="WWID input"
            )

        except TimeoutException:
            log.warning(f"[LOGIN][WARN] Timed out waiting for WWID field")
            return {"status": "failed", "reason": "wwid_field_timeout"}

        try:
            # Use send_text for the actual entry
            if not send_text(
                self.driver,
                (By.CSS_SELECTOR, "input[class*='fleet-operations-pwa__text-input__']"),
                login_id,
            ):
                return {"status": "failed", "reason": "wwid_entry_failed"}

            # Press Enter (special key → keep raw)
            self.driver.find_element(
                By.CSS_SELECTOR, "input[class*='fleet-operations-pwa__text-input__']"
            )
            if not click_element(self.driver, (By.XPATH, "//button[.//span[normalize-space()='Submit']]")):
                log.warning(f"[LOGIN][WARN] Could not click WWID submit button")
                return {"status": "failed", "reason": "wwid_submit_failed"}
            log.info(f"[LOGIN] WWID submitted via button")
            return {"status": "ok"}
            # time.sleep(5)


        except Exception as e:
            log.error(f"[LOGIN][ERROR] Unexpected error entering WWID: {e}")
            return {"status": "failed", "reason": "exception"}

    def login(self, username: str, password: str, login_id: str):
        """Perform login flow: email → password → stay signed in"""
        # Navigation via Navigator (SRP)
        
        log.info(f"[DEBUG] inside login()")
        Navigator(self.driver).go_to(
            "https://avisbudget.palantirfoundry.com/multipass/login", label="Login page"
        )

        # --- Email ---
        email_field = safe_wait(
            self.driver,
            10,
            EC.presence_of_element_located((By.NAME, "loginfmt")),
            "email_field",
        )
        if not email_field:
            log.warning(f"[LOGIN] Email field not found (timeout)")
            return {"status": "failed", "reason": "timeout_email_field"}

        log.info(f"[LOGIN] Typing email: {username}")
        email_field.send_keys(username)

        ## Click Next button to proceed to password
        log.info(f"[LOGIN] Clicking Next button after email")

        if not click_element(self.driver, (By.ID, "idSIButton9"), timeout=15):            
            return {"status": "failed", "reason": "timeout_next_button"}
        # --- Password ---
        password_field = safe_wait(
            self.driver,
            10,
            EC.presence_of_element_located((By.NAME, "passwd")),
            "password_field",
        )

        

        if not password_field:
            log.warning(f"[LOGIN] Password field not found (timeout)")
            return {"status": "failed", "reason": "timeout_password_field"}

        log.info(f"[LOGIN] Typing password")
        password_field.send_keys(password)
        log.info(f"[LOGIN] Password entered")

        log.info("[LOGIN] Clicking Sign in after password")
        time.sleep(5)
        if not click_element(self.driver, (By.ID, "idSIButton9"), desc="Sign in button"):
            return {"status": "failed", "reason": "click_password_next"}

        log.info(f"[LOGIN] Clicked Sign in appears to have worked")
        time.sleep(2)

        # --- Stay signed in? ---
        no_btn = safe_wait(
            self.driver,
            3,
            EC.element_to_be_clickable((By.ID, "idBtn_Back")),
            "stay_signed_in_no",
        )
        if no_btn:
            log.info(f"[LOGIN] Dismissing 'Stay signed in?' dialog with No")
            no_btn.click()
            time.sleep(1)
        else:
            log.info(f"[LOGIN] 'Stay signed in?' dialog not shown")

        return {"status": "ok"}

    def go_to_mobile_home(self):
        """Navigate from Foundry to Compass Mobile tab and verify WWID screen appears."""
        mobile_btn = safe_wait(
            self.driver,
            10,
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//a[@role='button']//span[contains(normalize-space(.), 'Compass Mobile')]",
                )
            ),
            "compass_mobile_button",
        )

        if not mobile_btn:
            log.warning(f"[LOGIN][WARN] Compass Mobile button not found")
            return {"status": "failed", "reason": "compass_mobile_button_missing"}

        # Save current tab count
        prev_tabs = len(self.driver.window_handles)

        log.info(f"[LOGIN] Clicking Compass Mobile button")
        mobile_btn.click()

        safe_wait(
            self.driver,
            10,
            lambda d: len(d.window_handles) > prev_tabs,
            desc="New tab to open"
        )


        # Confirm new tab appeared
        curr_tabs = len(self.driver.window_handles)
        if curr_tabs <= prev_tabs:
            log.warning(
                "[LOGIN][WARN] No new tab detected after clicking Compass Mobile"
            )
            return {"status": "failed", "reason": "no_new_tab"}

        # Switch to newest tab
        self.driver.switch_to.window(self.driver.window_handles[-1])
        log.info(f"[LOGIN] Switched to Compass Mobile tab")

        # Verify WWID field exists
        wwid_field = safe_wait(
            self.driver,
            10,
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[class*='fleet-operations-pwa__text-input__']")
            ),
            "wwid_input_field",
        )
        if not wwid_field:
            log.warning(
                "[LOGIN][WARN] WWID input not found after Compass Mobile launch"
            )
            return {"status": "failed", "reason": "wwid_field_missing"}

        log.info(f"[LOGIN] WWID input field detected")
        return {"status": "ok"}

    def ensure_user_context(self, login_id: str):
        """Ensure WWID is entered once Compass Mobile is loaded."""
        log.info(f"[LOGIN] Proceeding to WWID entry")
        return self.enter_wwid(login_id)

    def ensure_ready(self, username: str, password: str, login_id: str):
        """
        High-level pretest setup:
        1) ensure_logged_in
        2) go_to_mobile_home
        3) ensure_user_context(WWID)
        """
        log.info(f"[DEBUG] before ensure_logged_in")

        res = self.ensure_logged_in(username, password, login_id)
        log.debug(f"[LOGIN] ensure_logged_in - {res}")
        time.sleep(self.delay_seconds)
        if res["status"] != "ok":
            return res

        res = self.go_to_mobile_home()
        if res["status"] != "ok":
            return res

        res = self.ensure_user_context(login_id)
        return res
