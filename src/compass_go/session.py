"""Browser/profile lifecycle for Compass GO scraping.

Mirrors the profile-attach pattern used by WorkItems/create_workitem.py:
launches Edge with the user's signed-in profile so SSO is reused. Sync API
(matches the legacy subprocess worker contract — entry point is a plain
`python src/CompassGoParser.py`).
"""
from __future__ import annotations

import logging
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from playwright.sync_api import Page

log = logging.getLogger(__name__)

DEFAULT_ENTRY_URL = "https://go.avisbudget.palantirfoundry.com/"
DEFAULT_EDGE_USER_DATA_DIR = Path(os.getenv("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "User Data"
DEFAULT_EDGE_PROFILE_DIRECTORY = "Default"


def kill_running_edge() -> None:
    """Release the user-data-dir lock by terminating any running Edge."""
    try:
        check = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq msedge.exe", "/NH"],
            capture_output=True, text=True, check=False,
        )
        if "msedge.exe" not in check.stdout:
            return
        log.info("Closing running Edge to release profile lock")
        subprocess.run(
            ["taskkill", "/F", "/IM", "msedge.exe", "/T"],
            capture_output=True, text=True, check=False,
        )
    except OSError as exc:
        log.warning("Failed to terminate Edge processes: %s", exc)


def _resolve_user_data_dir() -> str:
    val = os.getenv("PLAYWRIGHT_EDGE_USER_DATA_DIR", "").strip()
    return val or str(DEFAULT_EDGE_USER_DATA_DIR)


def _resolve_profile_directory() -> str:
    val = os.getenv("PLAYWRIGHT_EDGE_PROFILE_DIRECTORY", "").strip()
    return val or DEFAULT_EDGE_PROFILE_DIRECTORY


def _resolve_headless() -> bool:
    return os.getenv("CGI_HEADLESS", "0").strip().lower() in {"1", "true", "yes", "on"}


class CompassGoSession:
    """Context manager that yields a Playwright Page bound to Compass GO."""

    def __init__(self, entry_url: str | None = None):
        self._entry_url = entry_url or os.getenv("COMPASS_GO_ENTRY_URL", DEFAULT_ENTRY_URL)

    @contextmanager
    def page(self) -> Iterator["Page"]:
        from playwright.sync_api import sync_playwright

        kill_running_edge()
        user_data_dir = _resolve_user_data_dir()
        profile_dir = _resolve_profile_directory()
        headless = _resolve_headless()
        log.info("Launching Edge profile: %s\\%s (headless=%s)", user_data_dir, profile_dir, headless)

        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(
                user_data_dir,
                channel="msedge",
                headless=headless,
                args=[f"--profile-directory={profile_dir}"],
                no_viewport=True,
            )
            try:
                page = context.new_page()
                page.goto(self._entry_url, wait_until="domcontentloaded")
                yield page
            finally:
                context.close()

