# flows/mva_navigation.py
# Shared MVA navigation utilities for Phase 7 and any other flow that needs
# to navigate Compass to a specific MVA page.
#
# All production scripts AND smoke/integration tests must use these functions.
# Navigation logic must not be duplicated in test files.

# ----------------------------------------------------------------------------
# AUTHOR:       Dirk Steele <dirk.avis@gmail.com>
# DATE:         2026-04-13
# DESCRIPTION:  Compass cold-start warm-up and per-MVA navigation.
#               Mirrors the proven pattern in GlassDataParser.py.
# VERSION:      1.0.0
# NOTES:        warmup_compass() must be called once after login before any
#               MVA is processed. navigate_to_mva() is called per-MVA.
# ----------------------------------------------------------------------------

import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config.config_loader import get_config
from pages.mva_input_page import MVAInputPage
from pages.vehicle_properties_page import VehiclePropertiesPage
from utils.logger import log


def _wait_for_input(driver, timeout: int = 30):
    """Return the MVA input field once it is clickable, or None on timeout."""
    for locator in MVAInputPage.CANDIDATES:
        try:
            return WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable(locator)
            )
        except Exception:
            continue
    return None


def warmup_compass(driver, timeout: int = 30) -> bool:
    """
    Enter a dummy MVA after login to prime the Compass app before processing
    real MVAs. The input becomes clickable before the app is fully initialized —
    entering a throwaway value and waiting for the vehicle detail panel to load
    confirms the app is ready.

    Returns True if warm-up succeeded, False on any failure.
    The dummy MVA value is read from config key 'warmup_mva' (default 50227203).
    """
    dummy_mva = str(get_config("warmup_mva", "50227203"))
    log.info(f"[NAV] Warming up Compass with dummy MVA {dummy_mva}...")
    try:
        input_field = _wait_for_input(driver, timeout=timeout)
        if not input_field:
            log.warning("[NAV] Warm-up failed — MVA input field not clickable")
            return False

        input_field.clear()
        input_field.send_keys(dummy_mva)

        # Wait for page structure to load before checking vehicle detail panel
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//button[normalize-space()='Add Work Item']")
                )
            )
        except Exception:
            log.warning("[NAV] Warm-up — page structure did not appear within timeout, proceeding anyway")

        # Confirm vehicle detail panel loaded — proves app is fully initialized
        props_page = VehiclePropertiesPage(driver)
        last8 = dummy_mva[-8:] if len(dummy_mva) >= 8 else dummy_mva
        echo = props_page.find_mva_echo(last8, timeout=10)
        if echo:
            log.info("[NAV] Compass app ready — vehicle detail panel confirmed")
        else:
            log.warning("[NAV] Warm-up MVA loaded but vehicle detail panel not confirmed — proceeding anyway")

        return True
    except Exception as e:
        log.error(f"[NAV] Warm-up failed with exception: {e}")
        return False


def navigate_to_mva(driver, mva: str, timeout: int = 30) -> bool:
    """
    Type an MVA into the Compass search field and wait for the page to load.

    Validates success by confirming:
    1. The 'Add Work Item' button is present (page structure loaded)
    2. The vehicle detail panel echoes the MVA (correct vehicle loaded)

    Returns True on success, False if navigation or validation fails.
    """
    log.info(f"[NAV] Navigating to MVA {mva}...")
    try:
        input_field = _wait_for_input(driver, timeout=timeout)
        if not input_field:
            log.error(f"[NAV] {mva} — MVA input field not clickable")
            return False

        input_field.clear()
        time.sleep(0.5)
        input_field.send_keys(mva)
        log.info(f"[NAV] {mva} — MVA entered")

        # Wait for 'Add Work Item' button — always present on a loaded MVA page
        # regardless of whether work items exist (unlike scan-record__ which only
        # renders when work items are present).
        try:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//button[normalize-space()='Add Work Item']")
                )
            )
        except Exception:
            log.error(f"[NAV] {mva} — 'Add Work Item' button did not appear within {timeout}s")
            return False

        # Validate vehicle detail panel loaded (plate, VIN, Desc, etc.)
        # Bad state: panel missing means Compass accepted the input but did not
        # navigate to the vehicle — app may not have been fully initialized.
        props_page = VehiclePropertiesPage(driver)
        last8 = mva[-8:] if len(mva) >= 8 else mva
        echo = props_page.find_mva_echo(last8, timeout=10)
        if not echo:
            log.error(
                f"[NAV] {mva} — vehicle detail panel not found. "
                f"Compass accepted the MVA but did not load vehicle properties."
            )
            return False

        log.info(f"[NAV] {mva} — page ready, vehicle detail confirmed")
        return True
    except Exception as e:
        log.error(f"[NAV] {mva} — navigation failed with exception: {e}")
        return False
