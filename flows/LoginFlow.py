from selenium.webdriver.remote.webdriver import WebDriver
from utils.logger import log
from pages.login_page import LoginPage
from pages.MicrosoftSSOPage import MicrosoftSSOPage
from config.config_loader import get_config

class LoginFlow:
    def __init__(self, driver: WebDriver):
        self.driver = driver
        self.login_page = LoginPage(driver)
        self.sso_page = MicrosoftSSOPage(driver)

    def login_handler(self, username: str, password: str, login_id: str) -> dict:
        log.info("[LOGIN_FLOW] Starting login handler.")

        # 1. Perform initial login (email, password, dismiss 'Stay signed in?')
        res = self.login_page.ensure_logged_in(username, password, login_id)
        if res["status"] != "ok":
            return res

        # 2. Check for and handle SSO page if present
        sso_present = self.sso_page.is_sso_page_present()
        if sso_present:
            log.info("[LOGIN_FLOW] Microsoft SSO page detected. Handling SSO.")
            sso_email = get_config('credentials.sso_email')
            if not sso_email:
                log.error("[LOGIN_FLOW] SSO email not found in config. Cannot proceed with SSO.")
                return {"status": "failed", "reason": "sso_email_missing"}
            try:
                self.sso_page.select_account(sso_email)
                log.info(f"[LOGIN_FLOW] Successfully selected SSO account: {sso_email}")
            except Exception as e:
                log.error(f"[LOGIN_FLOW] Failed to select SSO account {sso_email}: {e}")
                return {"status": "failed", "reason": "sso_selection_failed"}
        else:
            log.info("[LOGIN_FLOW] Microsoft SSO page not detected. Proceeding with standard login flow.")

        # 3. Navigate to Compass Mobile home and enter WWID
        res = self.login_page.go_to_mobile_home()
        if res["status"] != "ok":
            return res

        res = self.login_page.ensure_user_context(login_id)
        return res
