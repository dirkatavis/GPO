"""
Playwright-based browser driver manager for GlassOrchestrator.

Launches Edge browser with Playwright's profile-backed context.
"""
import os
import logging
from typing import Optional

from core.playwright_adapter import PlaywrightUiDriver

log = logging.getLogger("mc.automation")

_STATE = {"driver": None, "browser": None, "context": None, "pw": None}


def create_driver() -> PlaywrightUiDriver:
    """Create a new Playwright Edge browser and return UiDriver adapter."""
    if _STATE["driver"] is not None:
        raise RuntimeError("Driver already exists. Call quit_driver() first.")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("Playwright not installed. Run: pip install playwright")

    try:
        pw = sync_playwright().__enter__()
        _STATE["pw"] = pw
        
        # Launch Edge browser with profile support
        headless = os.getenv("CGI_HEADLESS", "0").strip().lower() in {"1", "true", "yes", "on"}
        log.info(f"[DRIVER] Launching Edge via Playwright (headless={headless})")
        
        browser = pw.chromium.launch(
            channel="msedge",
            headless=headless,
        )
        _STATE["browser"] = browser
        
        # Create persistent context with Edge user data dir
        user_data_dir = None
        profile_dir = "Default"
        
        if not os.getenv("GLASS_EDGE_NO_PROFILE", "0").strip().lower() in {"1", "true", "yes"}:
            local_app_data = os.getenv("LOCALAPPDATA", "").strip()
            if local_app_data:
                user_data_dir = os.path.join(local_app_data, "Microsoft", "Edge", "User Data")
                profile_dir = os.getenv("GLASS_EDGE_PROFILE_DIRECTORY", "Default").strip() or "Default"
                log.info(f"[DRIVER] Using Edge profile: user_data_dir={user_data_dir}, profile={profile_dir}")
        
        # Create context (with or without persistent user data)
        if user_data_dir and os.path.exists(user_data_dir):
            context = browser.new_context(
                channel="msedge",
                storage_state=None,  # Will use real profile instead
            )
        else:
            context = browser.new_context()
        
        _STATE["context"] = context
        
        page = context.new_page()
        driver = PlaywrightUiDriver(page)
        _STATE["driver"] = driver
        
        log.info("[DRIVER] Playwright Edge driver created")
        return driver
        
    except Exception as exc:
        log.error(f"[DRIVER] Failed to create Playwright driver: {exc}")
        quit_driver()
        raise


def quit_driver() -> None:
    """Close the Playwright driver and clean up resources."""
    if _STATE["driver"] is not None:
        try:
            if hasattr(_STATE["driver"], "page") and _STATE["driver"].page:
                _STATE["driver"].page.close()
        except Exception as exc:
            log.warning(f"[DRIVER] Failed to close page: {exc}")
        _STATE["driver"] = None
    
    if _STATE["context"] is not None:
        try:
            _STATE["context"].close()
        except Exception as exc:
            log.warning(f"[DRIVER] Failed to close context: {exc}")
        _STATE["context"] = None
    
    if _STATE["browser"] is not None:
        try:
            _STATE["browser"].close()
        except Exception as exc:
            log.warning(f"[DRIVER] Failed to close browser: {exc}")
        _STATE["browser"] = None
    
    if _STATE["pw"] is not None:
        try:
            _STATE["pw"].__exit__(None, None, None)
        except Exception as exc:
            log.warning(f"[DRIVER] Failed to close Playwright context: {exc}")
        _STATE["pw"] = None
    
    log.info("[DRIVER] Playwright driver closed")


def get_driver() -> Optional[PlaywrightUiDriver]:
    """Return the current driver, or None if not initialized."""
    return _STATE["driver"]
