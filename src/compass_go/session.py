"""Browser/profile lifecycle for Compass GO scraping.

Mirrors the profile-attach pattern used by WorkItems/create_workitem.py:
launches Edge with the user's signed-in profile so SSO is reused.

TODO: live-wire to playwright_prototype.config helpers
(`resolve_edge_user_data_dir`, `resolve_edge_profile_directory`,
`resolve_headless`) once Phase 3 begins.
"""
from __future__ import annotations

import logging
import subprocess
from contextlib import contextmanager
from typing import Iterator

log = logging.getLogger(__name__)


def kill_running_edge() -> None:
    """Release the user-data-dir lock by terminating any running Edge."""
    try:
        check = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq msedge.exe", "/NH"],
            capture_output=True, text=True, check=False,
        )
        if "msedge.exe" not in check.stdout:
            return
        log.info("Closing running Edge processes to release profile lock")
        subprocess.run(
            ["taskkill", "/F", "/IM", "msedge.exe", "/T"],
            capture_output=True, text=True, check=False,
        )
    except OSError as exc:
        log.warning("Failed to terminate Edge processes: %s", exc)


class CompassGoSession:
    """Context manager that yields a Playwright Page bound to Compass GO."""

    def __init__(self, entry_url: str = "https://go.avisbu..."):
        self._entry_url = entry_url

    @contextmanager
    def page(self) -> Iterator[object]:
        raise NotImplementedError(
            "CompassGoSession.page(): Phase 3 — wire to "
            "chromium.launch_persistent_context with profile attach"
        )
