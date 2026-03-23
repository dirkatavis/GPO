from selenium.webdriver.common.by import By

from utils.logger import log
from utils import ui_helpers


class HomePage:
    """Minimal HomePage page object exposing a single Supply Chain locator.

    Only responsibility: locate and click the Supply Chain control using the
    reliable `data-test-id='workshop-inline-button'` attribute.
    """

    SUPPLY_CHAIN_LOCATOR = (By.XPATH, "//a[@data-test-id='workshop-inline-button']")

    def __init__(self, driver):
        self.driver = driver

    def click_supply_chain(self) -> bool:
        """Click the Supply Chain control. Returns True on success."""
        return ui_helpers.click_element(self.driver, self.SUPPLY_CHAIN_LOCATOR, desc="Supply Chain", timeout=8)

