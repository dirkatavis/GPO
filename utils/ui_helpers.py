
# --- Imports ---
import os
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from utils.logger import log
from utils.project_paths import ProjectPaths

"""
UI Helper utilities for Selenium interactions.

Provides common helper functions for finding elements, clicking, sending text, etc.
"""

def _dump_artifacts(driver, prefix="debug"):
    """
    Debug utility: save screenshot and page source to artifacts directory.
    
    Args:
        driver: WebDriver instance
        prefix: Filename prefix for the artifacts
    """
    try:
        # Ensure artifacts directory exists
        artifacts_dir = os.path.join(ProjectPaths.get_project_root(), "artifacts")
        os.makedirs(artifacts_dir, exist_ok=True)
        
        # Save screenshot
        screenshot_path = os.path.join(artifacts_dir, f"{prefix}_screenshot.png")
        driver.save_screenshot(screenshot_path)
        log.info(f"Debug: Saved screenshot to {screenshot_path}")
        
        # Save page source  
        source_path = os.path.join(artifacts_dir, f"{prefix}_source.html")
        with open(source_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        log.info(f"Debug: Saved page source to {source_path}")
        
    except Exception as e:
        log.error(f"Failed to save debug artifacts: {e}")

def navigate_back_to_home(driver):
    """
    Navigate back to the home page by clicking the specific Fleet Operations PWA back arrow button.
    Raises exception if the back button is not found or navigation fails.
    """
    from selenium.webdriver.common.by import By
    import time
    
    def verify_home_page():
        """Verify we're back on the main page by checking for MVA input field."""
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='MVA'], input[id*='mva'], input[name*='mva']"))
            )
            log.info("[NAV] Successfully verified return to main page")
            return True
        except TimeoutException:
            log.error("[NAV] Could not verify main page MVA input field")
            return False
    
    try:
        log.info("[NAV] Attempting to navigate back to home page...")
        
        # Find and click the specific Fleet Operations PWA back button
        back_button = driver.find_element(By.CLASS_NAME, "fleet-operations-pwa__back-button__1bx4xor")
        back_button.click()
        log.info("[NAV] Successfully clicked Fleet Operations PWA back button")
        
        # Wait for navigation and verify home page
        time.sleep(2)
        if verify_home_page():
            log.info("[NAV] SUCCESS: Navigation back to home page completed successfully")
            return True
        else:
            log.error("[NAV] FAILURE: Back button clicked but home page verification failed")
            raise Exception("Back button clicked but home page verification failed")
        
    except NoSuchElementException:
        log.error("[NAV] FAILURE: Fleet Operations PWA back button not found - cannot navigate back to home")
        raise Exception("Fleet Operations PWA back button not found - cannot navigate back to home")
    except Exception as e:
        log.error(f"[NAV] FAILURE: Navigation back to home failed - {e}")
        raise Exception(f"Navigation back to home failed: {e}")

def find_elements(driver, locator, timeout=10):
    """
    Find all elements matching the locator within the timeout.
    Args:
        driver: WebDriver instance
        locator: Tuple of (By.TYPE, "selector")
        timeout: Timeout in seconds
    Returns:
        List of WebElements (may be empty if none found)
    """
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(locator)
        )
        return driver.find_elements(*locator)
    except TimeoutException:
        log.warning(f"Timeout waiting for elements: {locator}")
        return []
    except Exception as e:
        log.error(f"Error finding elements {locator}: {e}")
        return []


def safe_wait(driver, timeout, condition, desc="element"):
    """
    Safely wait for a condition with timeout.
    
    Args:
        driver: WebDriver instance
        timeout: Timeout in seconds
        condition: Expected condition or callable
        desc: Description for logging
        
    Returns:
        Element if found, None otherwise
    """
    try:
        element = WebDriverWait(driver, timeout).until(condition)
        return element
    except TimeoutException:
        log.warning(f"Timeout waiting for {desc}")
        return None
    except Exception as e:
        log.error(f"Error waiting for {desc}: {e}")
        return None


def find_element(driver, locator, timeout=10):
    """
    Find an element with explicit wait.
    
    Args:
        driver: WebDriver instance
        locator: Tuple of (By.TYPE, "selector")
        timeout: Timeout in seconds
        
    Returns:
        WebElement if found
        
    Raises:
        TimeoutException if element not found
    """
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located(locator)
    )


def click_element(driver, locator, timeout=10, desc=None):
    """
    Click an element with explicit wait.
    
    Args:
        driver: WebDriver instance
        locator: Tuple of (By.TYPE, "selector")
        timeout: Timeout in seconds
        desc: Description for logging
        
    Returns:
        bool: True if clicked successfully, False otherwise
    """
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(locator)
        )
        element.click()
        if desc:
            log.info(f"Clicked {desc}")
        return True
    except TimeoutException:
        log.warning(f"Timeout waiting to click {desc or 'element'}")
        return False
    except Exception as e:
        log.error(f"Error clicking {desc or 'element'}: {e}")
        return False


def send_text(driver, locator, text, timeout=10):
    """
    Send text to an input field with explicit wait.
    
    Args:
        driver: WebDriver instance
        locator: Tuple of (By.TYPE, "selector")
        text: Text to send
        timeout: Timeout in seconds
        
    Returns:
        bool: True if text sent successfully, False otherwise
    """
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(locator)
        )
        element.clear()
        element.send_keys(text)
        return True
    except TimeoutException:
        log.warning(f"Timeout waiting to send text")
        return False
    except Exception as e:
        log.error(f"Error sending text: {e}")
        return False


def is_element_present(driver, locator, timeout=5):
    """
    Check if an element is present within the given timeout.
    Args:
        driver: WebDriver instance
        locator: Tuple of (By.TYPE, "selector")
        timeout: Timeout in seconds
    Returns:
        bool: True if element is present, False otherwise
    """
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(locator)
        )
        return True
    except TimeoutException:
        return False
    except Exception as e:
        log.error(f"Error checking element presence: {e}")
        return False
