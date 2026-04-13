"""
E2E Tests — Phase 7 Glass Work Item Creation
=============================================

Requires a live Compass instance, valid credentials, and real test MVAs.
All tests are tagged @pytest.mark.e2e and skipped unless the opt-in env var is set.

To run:
    set GLASS_RUN_E2E_TESTS=1
    .venv\\Scripts\\python.exe -m pytest tests/test_e2e_glass_work_item.py -v -m e2e

Test MVAs must be set via environment variables before running:
    GLASS_E2E_MVA_EXISTING_ITEM   — MVA already has an open glass work item
    GLASS_E2E_MVA_CLEAN           — MVA with no existing glass work item or complaint
    GLASS_E2E_MVA_EXISTING_COMPLAINT — MVA with an existing glass complaint but no work item
    GLASS_E2E_MVA_SIDE            — MVA for side glass creation
    GLASS_E2E_MVA_REAR            — MVA for rear glass creation
    GLASS_E2E_MVA_INVALID         — MVA that will cause a failure (e.g. non-existent)
    GLASS_E2E_MVA_IDEMPOTENCY     — MVA to test idempotency (run twice)
"""

import os
import pytest

from core.driver_manager import create_driver, quit_driver
from config.config_loader import get_config
from flows.LoginFlow import LoginFlow
from flows.glass_work_item_phase import run_glass_work_item_phase
from flows.work_item_flow import check_existing_work_item


_RUN_E2E = os.getenv("GLASS_RUN_E2E_TESTS", "").strip().lower() in {"1", "true", "yes"}

pytestmark = pytest.mark.e2e


def _get_mva(env_var: str) -> str:
    """Return MVA from env var, or skip the test if not set."""
    val = os.getenv(env_var, "").strip()
    if not val:
        pytest.skip(f"E2E MVA not configured: set {env_var}")
    return val


@pytest.fixture(scope="module")
def driver():
    """Authenticated Compass WebDriver session shared across E2E tests."""
    if not _RUN_E2E:
        pytest.skip("E2E tests disabled — set GLASS_RUN_E2E_TESTS=1 to enable")

    drv = create_driver()
    username = os.getenv("GLASS_LOGIN_USERNAME") or get_config("username")
    password = os.getenv("GLASS_LOGIN_PASSWORD") or get_config("password")
    login_id = os.getenv("GLASS_LOGIN_ID") or get_config("login_id")

    login_flow = LoginFlow(drv)
    result = login_flow.login_handler(username, password, login_id)
    if result.get("status") != "ok":
        quit_driver()
        pytest.fail(f"E2E login failed: {result}")

    yield drv
    quit_driver()


# ─── E2E-1: Skip — existing open glass work item ─────────────────────────────


@pytest.mark.e2e
def test_e2e_skip_existing_open_work_item(driver):
    """
    Known MVA with an active open glass work item.
    check_existing_work_item() must return True; run_glass_work_item_phase()
    must skip it without creating a duplicate.
    """
    mva = _get_mva("GLASS_E2E_MVA_EXISTING_ITEM")

    assert check_existing_work_item(driver, mva, work_item_type="GLASS") is True

    result = run_glass_work_item_phase(
        driver,
        [{"mva": mva, "damage_type": "Replacement", "location": "WINDSHIELD"}],
    )
    assert result["skipped"] == 1
    assert result["created"] == 0
    assert result["processed"] == 1


# ─── E2E-2: Create — Windshield, no existing complaint ───────────────────────


@pytest.mark.e2e
def test_e2e_create_windshield_no_existing_complaint(driver):
    """
    Clean MVA with no existing glass work item or complaint.
    Phase 7 must create a work item with Windshield Crack complaint type.
    """
    mva = _get_mva("GLASS_E2E_MVA_CLEAN")

    result = run_glass_work_item_phase(
        driver,
        [{"mva": mva, "damage_type": "Replacement", "location": "WINDSHIELD"}],
    )
    assert result["created"] == 1
    assert result["skipped"] == 0
    assert result["failed"] == 0


# ─── E2E-3: Create — existing complaint association ──────────────────────────


@pytest.mark.e2e
def test_e2e_create_associates_existing_complaint(driver):
    """
    MVA with an existing glass complaint but no open work item.
    Phase 7 must associate the existing complaint rather than creating a new one,
    and the work item must be created successfully.
    """
    mva = _get_mva("GLASS_E2E_MVA_EXISTING_COMPLAINT")

    result = run_glass_work_item_phase(
        driver,
        [{"mva": mva, "damage_type": "Replacement", "location": "WINDSHIELD"}],
    )
    assert result["created"] == 1
    assert result["failed"] == 0


# ─── E2E-4: Create — Side glass ──────────────────────────────────────────────


@pytest.mark.e2e
def test_e2e_create_side_glass(driver):
    """
    location="SIDE" must map to Side/Rear Window Damage complaint type in Compass.
    Work item must be created successfully.
    """
    mva = _get_mva("GLASS_E2E_MVA_SIDE")

    result = run_glass_work_item_phase(
        driver,
        [{"mva": mva, "damage_type": "Replacement", "location": "SIDE"}],
    )
    assert result["created"] == 1
    assert result["failed"] == 0


# ─── E2E-5: Create — Rear glass ──────────────────────────────────────────────


@pytest.mark.e2e
def test_e2e_create_rear_glass(driver):
    """
    location="REAR" must map to Side/Rear Window Damage complaint type in Compass.
    Work item must be created successfully.
    """
    mva = _get_mva("GLASS_E2E_MVA_REAR")

    result = run_glass_work_item_phase(
        driver,
        [{"mva": mva, "damage_type": "Replacement", "location": "REAR"}],
    )
    assert result["created"] == 1
    assert result["failed"] == 0


# ─── E2E-6: Mixed manifest (3 MVAs) ──────────────────────────────────────────


@pytest.mark.e2e
def test_e2e_mixed_manifest_skipped_created_failed(driver):
    """
    Three-MVA manifest: one has an existing work item (skipped), one is clean
    (created), one is invalid (failed). All three must be attempted; counts correct.
    """
    mva_skip = _get_mva("GLASS_E2E_MVA_EXISTING_ITEM")
    mva_create = _get_mva("GLASS_E2E_MVA_CLEAN")
    mva_fail = _get_mva("GLASS_E2E_MVA_INVALID")

    manifest = [
        {"mva": mva_skip, "damage_type": "Replacement", "location": "WINDSHIELD"},
        {"mva": mva_create, "damage_type": "Replacement", "location": "WINDSHIELD"},
        {"mva": mva_fail, "damage_type": "Replacement", "location": "WINDSHIELD"},
    ]
    result = run_glass_work_item_phase(driver, manifest)

    assert result["processed"] == 3
    assert result["skipped"] == 1
    assert result["created"] == 1
    assert result["failed"] == 1


# ─── E2E-7: Idempotency ───────────────────────────────────────────────────────


@pytest.mark.e2e
def test_e2e_idempotency_second_run_skips(driver):
    """
    Run Phase 7 twice on the same MVA. Second run must detect the open work item
    created in the first run and skip — no duplicate work item created.
    """
    mva = _get_mva("GLASS_E2E_MVA_IDEMPOTENCY")
    manifest = [{"mva": mva, "damage_type": "Replacement", "location": "WINDSHIELD"}]

    # First run — creates the work item
    result1 = run_glass_work_item_phase(driver, manifest)
    assert result1["created"] == 1, f"First run did not create work item: {result1}"

    # Second run — must detect existing and skip
    result2 = run_glass_work_item_phase(driver, manifest)
    assert result2["skipped"] == 1, f"Second run did not skip: {result2}"
    assert result2["created"] == 0
