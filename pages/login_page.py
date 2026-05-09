import time
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC


from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


from core.navigator import Navigator
from config.config_loader import get_config
from utils.logger import log
from utils.ui_helpers import click_element, safe_wait, send_text


class LoginPage:
    def __init__(self, driver):
        self.driver = driver
        self.delay_seconds = get_config("delay_seconds", 4)
        self.login_url = get_config(
            "login_url",
            "https://avisbudget.palantirfoundry.com/multipass/login",
        )
        self.compass_app_label = get_config("compass_app_label", "Compass Mobile")

    def is_logged_in(self):
        """Check if Compass Mobile session is already authenticated."""
        
        log.info("[DEBUG] inside is_logged_in")
        elems = self.driver.find_elements(By.XPATH, f"//span[contains(text(),'{self.compass_app_label}')]")
        return len(elems) > 0

    def ensure_logged_in(self, username: str, password: str, login_id: str):
        # Always navigate first
        Navigator(self.driver).go_to(
            self.login_url, label="Login page"
        )

        # Check if already on the workspace page after redirection
        if "/workspace/module/view/" in self.driver.current_url or "/workspace/fleet-operations-pwa/" in self.driver.current_url:
            log.info("[LOGIN] Already on workspace page after redirection. Considering logged in.")
            return {"status": "ok"}

        # Handle automatic login redirection
        if "/multipass/automatic-login" in self.driver.current_url:
            log.info("[LOGIN] Automatic login page detected. Assuming login will succeed.")
            return {"status": "ok"}

        # Check if already on the workspace page after redirection
        if "/workspace/module/view/" in self.driver.current_url or "/workspace/fleet-operations-pwa/" in self.driver.current_url:
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

        except Exception as e:
            log.error(f"[LOGIN][ERROR] Unexpected error entering WWID: {e}")
            return {"status": "failed", "reason": "exception"}

    def ensure_user_context(self, login_id: str):
        """Ensure WWID is entered once Compass Mobile is loaded."""
        log.info(f"[LOGIN] Proceeding to WWID entry")
        return self.enter_wwid(login_id)

    def ensure_ready(self, username: str, password: str, login_id: str):
        """
        High-level pretest setup:
        1) ensure_logged_in
        2) ensure_user_context(WWID)
        """
        log.info(f"[DEBUG] before ensure_logged_in")

        res = self.ensure_logged_in(username, password, login_id)
        log.debug(f"[LOGIN] ensure_logged_in - {res}")
        time.sleep(self.delay_seconds)
        if res["status"] != "ok":
            return res

        res = self.ensure_user_context(login_id)
        return res
