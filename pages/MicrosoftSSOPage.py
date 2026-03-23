from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from utils.logger import log
from utils.ui_helpers import is_element_present, click_element

class MicrosoftSSOPage:
    """
    Page object for the Microsoft 'Pick an account' SSO dialog.
    """
    _SSO_PAGE_IDENTIFIER = (By.XPATH, "//div[contains(@aria-label, 'Pick an account') or contains(@data-testid, 'sso-page-identifier')]")
    _ACCOUNT_TILE_TEMPLATE = (By.XPATH, "//div[contains(@data-testid, 'account-tile') and .//div[contains(text(), '{email}')]]")

    def __init__(self, driver: WebDriver):
        self.driver = driver

    def is_sso_page_present(self, timeout: int = 10) -> bool:
        """
        Checks if the Microsoft SSO 'Pick an account' page is present.
        """
        log.debug(f"[SSO] Checking for SSO page presence with timeout {timeout}s.")
        return is_element_present(self.driver, self._SSO_PAGE_IDENTIFIER, timeout)

    def select_account(self, email: str, timeout: int = 10):
        """
        Selects the specified account from the SSO dialog.
        """
        log.info(f"[SSO] Attempting to select account: {email}")
        account_locator = (By.XPATH, self._ACCOUNT_TILE_TEMPLATE[1].format(email=email))
        click_element(self.driver, account_locator, f"SSO account tile for {email}", timeout)
        log.info(f"[SSO] Account {email} selected.")
