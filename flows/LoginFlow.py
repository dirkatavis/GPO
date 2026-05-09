from selenium.webdriver.remote.webdriver import WebDriver
from utils.logger import log
from pages.login_page import LoginPage

class LoginFlow:
    def __init__(self, driver: WebDriver):
        self.driver = driver
        self.login_page = LoginPage(driver)

    def login_handler(self, username: str, password: str, login_id: str) -> dict:
        log.info("[LOGIN_FLOW] Starting login handler.")

        # 1. Perform initial login (email, password, dismiss 'Stay signed in?')
        res = self.login_page.ensure_logged_in(username, password, login_id)
        if res["status"] != "ok":
            return res

        log.info("[LOGIN_FLOW] Proceeding directly to WWID entry.")
        res = self.login_page.ensure_user_context(login_id)
        return res
