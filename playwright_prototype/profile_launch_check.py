"""Profile launch verification helper for Edge + Playwright.

This script is a repeatable smoke check for the exact scenario we validated manually:
- Launch persistent Edge profile
- Verify reported profile path from edge://version
- Optionally perform a manual favorites-bar confirmation prompt

Exit codes:
- 0: all enabled checks passed
- 1: one or more checks failed
- 2: launch/runtime error
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from playwright_prototype.config import resolve_edge_profile_directory, resolve_edge_user_data_dir


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for profile verification."""
    parser = argparse.ArgumentParser(description="Verify Edge profile launch state")
    parser.add_argument(
        "--edge-user-data-dir",
        default=str(resolve_edge_user_data_dir()),
        help="Edge user data directory (defaults to resolved config/env value)",
    )
    parser.add_argument(
        "--edge-profile-directory",
        default=resolve_edge_profile_directory(),
        help="Edge profile directory, for example 'Profile 1' or 'Default'",
    )
    parser.add_argument(
        "--check-url",
        default="https://m365.cloud.microsoft/chat",
        help="URL to open after edge://version check to optionally inspect auth state",
    )
    parser.add_argument(
        "--check-auth",
        action="store_true",
        help="Enable authentication URL check after launch (disabled by default)",
    )
    parser.add_argument(
        "--no-manual",
        action="store_true",
        help="Skip manual prompt for favorites bar visibility",
    )
    return parser.parse_args()


def _manual_favorites_prompt() -> bool:
    """Prompt operator for manual favorites bar confirmation.

    Returns:
        True if operator confirms favorites bar is visible; otherwise False.
    """
    answer = input("Is the favorites bar visible in Edge? [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def main() -> int:
    """Run profile launch verification and return process exit code."""
    args = _parse_args()
    user_data_dir = Path(args.edge_user_data_dir)
    profile_dir = args.edge_profile_directory.strip()

    if not user_data_dir.exists():
        print(f"[FAIL] Edge user data dir does not exist: {user_data_dir}")
        return 1
    if not profile_dir:
        print("[FAIL] --edge-profile-directory is blank")
        return 1

    print(f"[INFO] Launching Edge with user_data_dir={user_data_dir} profile={profile_dir}")

    try:
        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                channel="msedge",
                headless=False,
                args=[f"--profile-directory={profile_dir}", "--start-maximized"],
            )
            try:
                page = context.pages[0] if context.pages else context.new_page()

                page.goto("edge://version", wait_until="domcontentloaded")
                body_text = page.locator("body").inner_text(timeout=15000)

                expected_fragment = os.path.join("User Data", profile_dir).lower()
                profile_ok = expected_fragment in body_text.lower()
                print(f"[CHECK] edge://version profile path contains '...{expected_fragment}': {profile_ok}")

                auth_ok = True
                if args.check_auth:
                    page.goto(args.check_url, wait_until="domcontentloaded")
                    current_url = page.url
                    login_blockers = ("login.microsoftonline.com", "login.live.com", "/signin")
                    auth_ok = not any(token in current_url for token in login_blockers)
                    print(f"[CHECK] session appears authenticated at {current_url}: {auth_ok}")

                manual_ok = True
                if not args.no_manual:
                    manual_ok = _manual_favorites_prompt()
                    print(f"[CHECK] operator confirmed favorites bar visible: {manual_ok}")

                passed = profile_ok and auth_ok and manual_ok
                print(f"[RESULT] {'PASS' if passed else 'FAIL'}")
                return 0 if passed else 1
            finally:
                context.close()
    except Exception as exc:  # pragma: no cover - smoke runtime path
        print(f"[ERROR] Failed to launch/check profile: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
