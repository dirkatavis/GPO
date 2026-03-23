from selenium.webdriver.common.by import By

from utils.logger import log
from utils.ui_helpers import find_element


class VehiclePropertiesPage:
    def __init__(self, driver):
        self.driver = driver

    def find_mva_echo(self, last8: str, timeout: int = 8):
        """Return the element where the vehicle properties panel echoes the given last8 MVA."""
        try:
            xp_by_label = (
                "//div[contains(@class,'vehicle-properties-container')]"
                "//div[contains(@class,'vehicle-property__')]"
                "[div[contains(@class,'vehicle-property-name')][normalize-space()='MVA']]"
                f"/div[contains(@class,'vehicle-property-value')][contains(normalize-space(), '{last8}')]"
            )
            return find_element(self.driver, (By.XPATH, xp_by_label), timeout=timeout)
        except Exception:
            try:
                xp_any_value_contains = (
                    "//div[contains(@class,'vehicle-properties-container')]"
                    f"//div[contains(@class,'vehicle-property-value')][contains(normalize-space(), '{last8}')]"
                )
                return find_element(
                    self.driver, (By.XPATH, xp_any_value_contains), timeout=3
                )
            except Exception:
                log.error(
                    "[MVA][ERROR] echoed value not found (looked for last8='{last8}')"
                )
                return None
