from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utils.logger import log


class Navigator:
    def __init__(self, driver):
        self.driver = driver

    def go_to(self, url: str, label: str = "page", verify: bool = True):
        """Navigate to a URL. Optionally call verify afterwards."""
        try:
            log.info(f"[NAV] Navigating to {label} - {url}")
        except UnicodeEncodeError:
            log.info(f"[NAV] Navigating to {label} - {url.encode('utf-8', 'ignore').decode('utf-8')}")
        self.driver.get(url)

        if verify:
            return self.verify(url=url)
        return {"status": "ok"}

    def verify(self, url: str = None, check_locator=None, timeout: int = 15):
        """Verify page has loaded (readyState, URL match, optional element)."""
        WebDriverWait(self.driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        if url and not self.driver.current_url.startswith(url):
            log.warning(f"[NAV] Expected {url}, got {self.driver.current_url}")
            return {"status": "failed", "reason": "url_mismatch"}

        if check_locator:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(check_locator)
            )
            log.info(f"[NAV] Verified element {check_locator}")

        return {"status": "ok"}
