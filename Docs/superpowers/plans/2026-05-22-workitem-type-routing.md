# Work Item Type Routing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalize work item scripts (create/close/verify) to support multiple complaint types (Glass, PM) via a unified CSV schema, and consolidate user-facing scripts into `WorkItems/`.

**Architecture:** The `playwright_prototype/steps.py` layer becomes type-aware: `COMPLAINT_TYPE_PATTERNS` moves there from `close_workitem.py`, `check_existing_glass_work_item` → `check_existing_work_item(page, mva, type)`, `select_glass_opcode` → `select_opcode(page, type)`, and `handle_complaint_dialog` gains a PM branch after the drivability click. User-facing scripts move to `WorkItems/` with a `sys.path` fix so imports from the repo-root packages still resolve. CMD launchers and default CSV paths are updated.

**Tech Stack:** Python 3.13, Playwright async_api, pytest

---

## File Map

| File | Action |
|------|--------|
| `WorkItems/` | Create directory |
| `WorkItems/create_workitem.csv` | Create — updated schema from `playwright_prototype/sample_mvas.csv` |
| `WorkItems/close_workitem.csv` | Create — new, empty with header/comment block |
| `WorkItems/create_workitem.py` | Move from root + sys.path fix + Type column + PM routing + inline `process_mva` |
| `WorkItems/close_workitem.py` | Move from root + sys.path fix + import `COMPLAINT_TYPE_PATTERNS` from steps + comment-line skipping |
| `WorkItems/verify_workitem.py` | Move from root + sys.path fix (no other changes) |
| `playwright_prototype/steps.py` | Add `COMPLAINT_TYPE_PATTERNS`; rename `check_existing_glass_work_item` → `check_existing_work_item(page, mva, type)`; add PM branch to `handle_complaint_dialog`; rename `select_glass_opcode` → `select_opcode(page, type)` |
| `config/config.json` | Add `pm_opcode: "PM Gas"` key |
| `playwright_prototype/main.py` | Add deprecation comment; update imports/calls for renamed functions |
| `archive/smoke_test_workitem.py` | Move from root |
| `Run-CreateWorkItems.cmd` | Update script + CSV paths |
| `Run-CloseWorkItems.cmd` | Update script + CSV paths |
| `Run-VerifyWorkItems.cmd` | Update script + CSV paths |
| `Run-SmokeWorkItems.cmd` | Update script + CSV paths |
| `tests/test_steps_complaint_dialog.py` | Update `handle_complaint_dialog` calls to include `type` argument |

> **Log file note:** `utils/logger.py` derives the log file name from `sys.argv[0]` and always writes to `log/<scriptname>.log` at the working directory (repo root). Scripts in `WorkItems/` will log to `log/create_workitem.log` etc. — no code change needed.

---

## Task 1: Scaffold WorkItems/ folder and CSVs

**Files:**
- Create: `WorkItems/` (directory)
- Create: `WorkItems/create_workitem.csv`
- Create: `WorkItems/close_workitem.csv`

- [ ] **Step 1: Create the WorkItems directory**

```powershell
New-Item -ItemType Directory -Path "WorkItems"
```

- [ ] **Step 2: Create WorkItems/create_workitem.csv**

Full content of `WorkItems/create_workitem.csv`:

```
# create_workitem.csv — input for WorkItems/create_workitem.py
# (close_workitem.csv uses the same schema)
#
# Columns:
#   mva      — MVA number (required)
#   Type     — Work item type: Glass, PM               (required; defaults to Glass if omitted)
#   location — Glass only: glass area code             (required for Glass, e.g. WS, BW, FLD)
#   action   — Glass/WS only: Replace or Repair        (required when Type=Glass and location=WS)
#
# Notes:
#   - Repair is only valid for windshields (location=WS)
#   - Non-WS glass locations always map to Side/Rear Window Damage regardless of action
#   - PM rows leave location and action blank
#   - Lines starting with # are ignored
#
mva,Type,location,action
```

- [ ] **Step 3: Create WorkItems/close_workitem.csv**

Full content of `WorkItems/close_workitem.csv`:

```
# close_workitem.csv — input for WorkItems/close_workitem.py
#
# Columns:
#   mva      — MVA number (required)
#   Type     — Work item type: Glass, PM  (required)
#
# Notes:
#   - Lines starting with # are ignored
#   - Rows with a blank mva are skipped
#
mva,Type
```

- [ ] **Step 4: Verify files exist**

```powershell
Test-Path "WorkItems\create_workitem.csv"
Test-Path "WorkItems\close_workitem.csv"
```

Expected: both return `True`

- [ ] **Step 5: Commit**

```bash
git add WorkItems/create_workitem.csv WorkItems/close_workitem.csv
git commit -m "feat: scaffold WorkItems/ folder with CSV templates"
```

---

## Task 2: Add pm_opcode to config

**Files:**
- Modify: `config/config.json`

- [ ] **Step 1: Write the failing test**

Add to a new test file `tests/test_config_pm_opcode.py`:

```python
"""Verify pm_opcode is present in config."""
from config.config_loader import get_config


def test_pm_opcode_returns_pm_gas():
    assert get_config("pm_opcode") == "PM Gas"


def test_pm_opcode_has_comment():
    """Config comment key exists (documents the setting)."""
    import json
    from pathlib import Path
    cfg = json.loads((Path("config/config.json")).read_text(encoding="utf-8"))
    assert "pm_opcode_comment" in cfg
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv\Scripts\python.exe -m pytest tests/test_config_pm_opcode.py -v
```

Expected: FAIL — `AssertionError` (key not found)

- [ ] **Step 3: Add pm_opcode to config/config.json**

Insert after the `glass_opcode_fallback` block (after line 18 of current config.json):

```json
	"pm_opcode_comment": "Opcode name for PM work items. Set to null to skip opcode selection for PM.",
	"pm_opcode": "PM Gas",
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv\Scripts\python.exe -m pytest tests/test_config_pm_opcode.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config/config.json tests/test_config_pm_opcode.py
git commit -m "feat: add pm_opcode config key (PM Gas)"
```

---

## Task 3: Update steps.py — move COMPLAINT_TYPE_PATTERNS, rename functions

**Files:**
- Modify: `playwright_prototype/steps.py`
- Modify: `tests/test_steps_complaint_dialog.py`

This task renames two functions and moves `COMPLAINT_TYPE_PATTERNS` into steps.py. The handle_complaint_dialog PM branch is a separate task (Task 4).

- [ ] **Step 1: Write failing tests for COMPLAINT_TYPE_PATTERNS in steps**

Add to `tests/test_steps_complaint_dialog.py` (append to file):

```python
class TestComplaintTypePatterns:
    """COMPLAINT_TYPE_PATTERNS in steps.py matches the correct tile text."""

    def test_glass_pattern_matches_glass(self):
        from playwright_prototype.steps import COMPLAINT_TYPE_PATTERNS
        assert COMPLAINT_TYPE_PATTERNS["Glass"].search("Glass Damage")

    def test_glass_pattern_matches_windshield(self):
        from playwright_prototype.steps import COMPLAINT_TYPE_PATTERNS
        assert COMPLAINT_TYPE_PATTERNS["Glass"].search("Windshield Crack")

    def test_pm_pattern_matches_pm(self):
        from playwright_prototype.steps import COMPLAINT_TYPE_PATTERNS
        assert COMPLAINT_TYPE_PATTERNS["PM"].search("PM Gas")

    def test_glass_pattern_does_not_match_pm(self):
        from playwright_prototype.steps import COMPLAINT_TYPE_PATTERNS
        assert not COMPLAINT_TYPE_PATTERNS["Glass"].search("PM preventive maintenance")

    def test_check_existing_work_item_importable(self):
        """Renamed function must be importable from steps."""
        from playwright_prototype.steps import check_existing_work_item
        assert callable(check_existing_work_item)

    def test_select_opcode_importable(self):
        """Renamed function must be importable from steps."""
        from playwright_prototype.steps import select_opcode
        assert callable(select_opcode)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv\Scripts\python.exe -m pytest tests/test_steps_complaint_dialog.py::TestComplaintTypePatterns -v
```

Expected: FAIL — `ImportError` (names not yet in steps.py)

- [ ] **Step 3: Add COMPLAINT_TYPE_PATTERNS to playwright_prototype/steps.py**

At the top of `playwright_prototype/steps.py`, after the existing imports (after `from config.config_loader import get_config`), add:

```python
_GLASS_PATTERN = re.compile(r"glass|windshield|crack|chip|window", re.I)
_PM_PATTERN = re.compile(r"PM", re.I)

COMPLAINT_TYPE_PATTERNS: dict[str, re.Pattern] = {
    "Glass": _GLASS_PATTERN,
    "PM":    _PM_PATTERN,
}
```

Note: `re` is not yet imported in steps.py — add it to the imports block at the top:

```python
import re
```

- [ ] **Step 4: Rename check_existing_glass_work_item → check_existing_work_item**

Replace the full function body of `check_existing_glass_work_item` in steps.py with:

```python
class ExistingWorkItemError(Exception):
    """Raised when an open work item of the requested type already exists for an MVA."""


async def check_existing_work_item(page: Page, mva: str, type: str) -> None:
    """Raise ExistingWorkItemError if an open work item of the given type already exists.

    Uses COMPLAINT_TYPE_PATTERNS[type] to match tiles. Inspects work items on the
    vehicle page — aborts for this MVA if a matching open tile is found.
    """
    pattern = COMPLAINT_TYPE_PATTERNS.get(type, _GLASS_PATTERN)
    log.info("[STEPS] %s — checking for existing open %s work item", mva, type)
    try:
        container = page.locator('[class*="fleet-operations-pwa__scan-record__"]').first
        try:
            await container.wait_for(state="visible", timeout=8_000)
        except Exception:
            log.info("[STEPS] %s — no work items container found, safe to proceed", mva)
            return

        open_item = page.locator(
            '[class*="fleet-operations-pwa__scan-record__"]'
        ).filter(has_text=pattern).filter(has_text=re.compile(r"open", re.I))
        count = await open_item.count()
        if count > 0:
            tile_text = await open_item.first.inner_text()
            raise ExistingWorkItemError(
                f"{mva} — open {type} work item already exists: {tile_text.strip()!r}"
            )
        log.info("[STEPS] %s — no open %s work item found, safe to proceed", mva, type)
    except ExistingWorkItemError:
        raise
    except Exception as exc:
        raise RuntimeError(f"[STEPS] check_existing_work_item failed for {mva}: {exc}") from exc
```

- [ ] **Step 5: Rename select_glass_opcode → select_opcode**

Replace the full function body of `select_glass_opcode` in steps.py with:

```python
async def select_opcode(page: Page, type: str) -> None:
    """Select the appropriate opcode for the given work item type.

    Glass: selects glass_opcode_primary (default 'Glass Repair/Replace').
    PM: selects pm_opcode config value (default 'PM Gas'); skips step if pm_opcode is null.
    """
    if type == "PM":
        pm_opcode = get_config("pm_opcode", None)
        if pm_opcode is None:
            log.info("[STEPS] PM: pm_opcode is null — skipping opcode selection")
            return
        opcode_label = str(pm_opcode)
    else:
        opcode_label = str(get_config("glass_opcode_primary", "Glass Repair/Replace"))

    log.info("[STEPS] Selecting '%s' OpCode", opcode_label)
    try:
        await page.locator('[class*="opCodeText"]').first.wait_for(
            state="visible", timeout=15_000
        )
        target = page.get_by_text(opcode_label, exact=True)
        await target.scroll_into_view_if_needed()
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await target.click(timeout=10_000)
        await page.get_by_role("button", name="Create Work Item").wait_for(
            state="visible", timeout=15_000
        )
        log.info("[STEPS] OpCode '%s' selected — 'Create Work Item' button visible", opcode_label)
    except Exception as exc:
        raise RuntimeError(f"[STEPS] select_opcode failed for type={type}: {exc}") from exc
```

- [ ] **Step 6: Update existing test calls for the new handle_complaint_dialog signature**

The existing tests in `test_steps_complaint_dialog.py` call `handle_complaint_dialog(page, mva, location, action)`. The function signature will gain `type` as the 3rd positional argument in Task 4. Update all 6 existing calls now so tests stay green after Task 4.

In `tests/test_steps_complaint_dialog.py`, replace every call of the form:
```python
asyncio.run(handle_complaint_dialog(page, "59002156", "WS", "Replace"))
```
with:
```python
asyncio.run(handle_complaint_dialog(page, "59002156", "Glass", "WS", "Replace"))
```

And:
```python
asyncio.run(handle_complaint_dialog(page, "99999999", "RW", "Replace"))
```
with:
```python
asyncio.run(handle_complaint_dialog(page, "99999999", "Glass", "RW", "Replace"))
```

And:
```python
asyncio.run(handle_complaint_dialog(page, "99999999", "WS", "Repair"))
```
with:
```python
asyncio.run(handle_complaint_dialog(page, "99999999", "Glass", "WS", "Repair"))
```

- [ ] **Step 7: Run all steps tests to verify pass**

```bash
.venv\Scripts\python.exe -m pytest tests/test_steps_complaint_dialog.py tests/test_steps_navigation.py -v
```

Expected: All PASS (complaint_dialog tests still pass because `handle_complaint_dialog` signature hasn't changed yet — the `type` arg update happens in Task 4)

- [ ] **Step 8: Commit**

```bash
git add playwright_prototype/steps.py tests/test_steps_complaint_dialog.py
git commit -m "feat: add COMPLAINT_TYPE_PATTERNS to steps; rename check_existing_work_item, select_opcode"
```

---

## Task 4: Add PM branch to handle_complaint_dialog

**Files:**
- Modify: `playwright_prototype/steps.py`

- [ ] **Step 1: Replace handle_complaint_dialog in playwright_prototype/steps.py**

Replace the entire `handle_complaint_dialog` function with the version below. The signature gains `type` as the 3rd positional argument. The existing-complaint path is generalized via `COMPLAINT_TYPE_PATTERNS`. The new-complaint path branches after drivability: Glass follows the existing logic; PM clicks the "PM" button, waits for the Additional Info screen, and submits.

```python
async def handle_complaint_dialog(page: Page, mva: str, type: str, location: str, action: str, step_delay_ms: int = 0) -> None:
    """Associate an existing complaint or create a new one, branching by type (Glass or PM).

    Existing path: find matching complaint tile → click → Next (advances to mileage).
    New path: Add New Complaint → Drivability → type-specific buttons → Submit Complaint.
    Both paths leave the page on the mileage dialog for complete_mileage_dialog().
    """
    log.info("[STEPS] %s — handling complaint dialog (type=%s location=%s action=%s)", mva, type, location, action)

    async def delay():
        if step_delay_ms:
            await page.wait_for_timeout(step_delay_ms)

    try:
        await page.wait_for_timeout(2_000)

        pattern = COMPLAINT_TYPE_PATTERNS.get(type, _GLASS_PATTERN)
        existing_tile = page.locator(
            '[class*="fleet-operations-pwa__complaintItem__"]'
        ).filter(has_text=pattern)

        if await existing_tile.count() > 0:
            log.info("[STEPS] %s — found existing %s complaint, associating", mva, type)
            await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
            await existing_tile.first.click(timeout=5_000);  await delay()
            await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
            await page.get_by_role("button", name="Next").click(timeout=10_000)
            mileage_appeared = False
            for locator in [
                page.get_by_role("heading", name=re.compile(r"Mileage", re.I)),
                page.get_by_text(re.compile(r"\bMileage\b", re.I)),
                page.locator('input[placeholder*="Mileage" i], input[aria-label*="Mileage" i]'),
            ]:
                try:
                    await locator.first.wait_for(state="visible", timeout=8_000)
                    mileage_appeared = True
                    break
                except Exception:
                    continue
            if not mileage_appeared:
                raise RuntimeError(f"[STEPS] {mva} — existing complaint Next did not advance to mileage dialog")
            return

        # No existing complaint — create new
        log.info("[STEPS] %s — no existing %s complaint, creating new", mva, type)
        add_btn = page.locator(
            "//button[.//p[contains(text(),'Add New Complaint')] or .//p[contains(text(),'Create New Complaint')]]"
            " | //button[normalize-space()='Add New Complaint']"
            " | //button[normalize-space()='Create New Complaint']"
        ).first
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await add_btn.click(timeout=10_000);  await delay()

        drivability = str(get_config("default_drivability", "Yes"))
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await page.get_by_role("button", name=drivability).click(timeout=10_000)
        log.info("[STEPS] %s — drivability: %s", mva, drivability);  await delay()

        if type == "PM":
            await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
            await page.get_by_role("button", name="PM").click(timeout=10_000)
            log.info("[STEPS] %s PM: PM button clicked", mva);  await delay()

            # Wait for Additional Info screen — leave checkbox at default (unchecked), skip photo
            await page.locator('[class*="fleet-operations-pwa__"]').filter(
                has_text=re.compile(r"additional info", re.I)
            ).first.wait_for(state="visible", timeout=15_000)
            log.info("[STEPS] %s PM: Additional Info screen visible", mva);  await delay()

            pre_submit_url = page.url
            await _click_submit_complaint(page, mva)
            log.info("[STEPS] %s PM: PM complaint submitted", mva)

            if not await _wait_for_post_submit_progress(page, pre_submit_url):
                pm_tile_post = page.locator(
                    '[class*="fleet-operations-pwa__complaintItem__"]'
                ).filter(has_text=_PM_PATTERN)
                if await pm_tile_post.count() > 0:
                    log.info("[STEPS] %s PM: post-submit complaint list shown, associating", mva)
                    await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
                    await pm_tile_post.first.click(timeout=5_000);  await delay()
                    await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
                    await page.get_by_role("button", name="Next").click(timeout=10_000)

                if not await _wait_for_post_submit_progress(page, pre_submit_url):
                    raise RuntimeError(
                        f"[STEPS] {mva} PM — submit completed without mileage/url transition"
                    )
            return

        # Glass path
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await page.get_by_role("button", name="Glass Damage").click(timeout=10_000);  await delay()

        damage_label = _map_damage_type(location, action)
        log.info("[STEPS] %s — selecting damage type: %s", mva, damage_label)
        await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
        await page.locator(f'//button[.//h1[text()="{damage_label}"]]').click(timeout=10_000);  await delay()

        pre_submit_url = page.url
        await _click_submit_complaint(page, mva)
        log.info("[STEPS] %s — new glass complaint submitted", mva)

        if await _wait_for_post_submit_progress(page, pre_submit_url):
            return

        log.warning(
            "[STEPS] %s — submit did not show mileage/url transition; attempting complaint association fallback",
            mva,
        )
        await page.wait_for_timeout(2_000)
        glass_tile_post = page.locator(
            '[class*="fleet-operations-pwa__complaintItem__"]'
        ).filter(has_text=_GLASS_PATTERN)
        if await glass_tile_post.count() > 0:
            log.info("[STEPS] %s — post-submit: complaint list shown, associating new complaint", mva)
            await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
            await glass_tile_post.first.click(timeout=5_000);  await delay()
            await page.wait_for_timeout(BUTTON_PUSH_DELAY_MS)
            await page.get_by_role("button", name="Next").click(timeout=10_000)

        if not await _wait_for_post_submit_progress(page, pre_submit_url):
            raise RuntimeError(
                f"[STEPS] {mva} — submit completed without mileage/url transition; backend may have rejected write"
            )

    except Exception as exc:
        raise RuntimeError(f"[STEPS] handle_complaint_dialog failed for {mva}: {exc}") from exc
```

- [ ] **Step 2: Run steps tests**

```bash
.venv\Scripts\python.exe -m pytest tests/test_steps_complaint_dialog.py tests/test_steps_navigation.py -v
```

Expected: All PASS (existing-path tests call with `"Glass"` 3rd arg — set up in Task 3 Step 6)

- [ ] **Step 3: Commit**

```bash
git add playwright_prototype/steps.py
git commit -m "feat: add PM branch to handle_complaint_dialog; generalize existing-complaint path"
```

---

## Task 5: Update playwright_prototype/main.py (deprecated)

**Files:**
- Modify: `playwright_prototype/main.py`

main.py is deprecated (no CMD file calls it). Update its imports so renamed functions don't cause import errors at startup. All calls get `type="Glass"` hardcoded since this script is Glass-only.

- [ ] **Step 1: Update imports and calls in playwright_prototype/main.py**

Replace the imports block:
```python
from playwright_prototype.steps import (
    ExistingWorkItemError,
    check_existing_glass_work_item,
    click_add_work_item,
    complete_mileage_dialog,
    confirm_completion,
    create_work_item,
    handle_complaint_dialog,
    navigate_to_mva,
    select_glass_opcode,
    warmup_compass,
)
```
with:
```python
# DEPRECATED: this prototype is superseded by WorkItems/create_workitem.py
# Do not add new features here. Remove once WorkItems/ is confirmed stable.
from playwright_prototype.steps import (
    ExistingWorkItemError,
    check_existing_work_item,
    click_add_work_item,
    complete_mileage_dialog,
    confirm_completion,
    create_work_item,
    handle_complaint_dialog,
    navigate_to_mva,
    select_opcode,
    warmup_compass,
)
```

In `process_mva`, update the two renamed calls:
```python
# Change:
    await check_existing_glass_work_item(page, mva);
# To:
    await check_existing_work_item(page, mva, "Glass");
```

```python
# Change:
    await handle_complaint_dialog(page, mva, location, action, step_delay_ms);
# To:
    await handle_complaint_dialog(page, mva, "Glass", location, action, step_delay_ms);
```

```python
# Change:
    await select_glass_opcode(page);
# To:
    await select_opcode(page, "Glass");
```

In the `--pause` block, update the step labels accordingly:
```python
# Change:
    await step(check_existing_glass_work_item(page, mva), ...)
# To:
    await step(check_existing_work_item(page, mva, "Glass"), ...)
```

```python
# Change:
    await step(handle_complaint_dialog(page, mva, location, action, step_delay_ms), ...)
# To:
    await step(handle_complaint_dialog(page, mva, "Glass", location, action, step_delay_ms), ...)
```

```python
# Change:
    await step(select_glass_opcode(page), ...)
# To:
    await step(select_opcode(page, "Glass"), ...)
```

- [ ] **Step 2: Run the full test suite to verify no regressions**

```bash
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add playwright_prototype/main.py
git commit -m "chore: update deprecated main.py for renamed steps functions"
```

---

## Task 6: Create WorkItems/create_workitem.py

**Files:**
- Create: `WorkItems/create_workitem.py` (from root `create_workitem.py` with changes)

> The root `create_workitem.py` is left in place and will be removed in Task 10 after CMD files are updated and confirmed working.

- [ ] **Step 1: Write failing tests for Type-column CSV loading**

Create `tests/test_create_workitem_csv.py`:

```python
"""Tests for _build_create_targets Type-column handling in WorkItems/create_workitem.py."""
import sys
import csv
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest


def _write_csv(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "test.csv"
    p.write_text(content, encoding="utf-8")
    return p


class TestBuildCreateTargets:

    def _run(self, tmp_path, csv_content, extra_args=None):
        from WorkItems.create_workitem import _build_create_targets
        csv_path = _write_csv(tmp_path, csv_content)
        args = MagicMock()
        args.csv = str(csv_path)
        args.mva = None
        args.action = None
        if extra_args:
            for k, v in extra_args.items():
                setattr(args, k, v)
        return _build_create_targets(args)

    def test_glass_row_with_ws_location(self, tmp_path):
        targets = self._run(tmp_path, "mva,Type,location,action\n12345,Glass,WS,Replace\n")
        assert len(targets) == 1
        assert targets[0] == {"mva": "12345", "type": "Glass", "location": "WS", "action": "Replace"}

    def test_pm_row_no_location_action(self, tmp_path):
        targets = self._run(tmp_path, "mva,Type,location,action\n67890,PM,,\n")
        assert len(targets) == 1
        assert targets[0] == {"mva": "67890", "type": "PM", "location": "", "action": ""}

    def test_missing_type_defaults_to_glass(self, tmp_path):
        targets = self._run(tmp_path, "mva,Type,location,action\n11111,,WS,Replace\n")
        assert targets[0]["type"] == "Glass"

    def test_comment_lines_skipped(self, tmp_path):
        csv_content = (
            "# this is a comment\n"
            "mva,Type,location,action\n"
            "# another comment\n"
            "22222,Glass,WS,Replace\n"
        )
        targets = self._run(tmp_path, csv_content)
        assert len(targets) == 1
        assert targets[0]["mva"] == "22222"

    def test_blank_mva_skipped(self, tmp_path):
        targets = self._run(tmp_path, "mva,Type,location,action\n,Glass,WS,Replace\n33333,Glass,WS,Replace\n")
        assert len(targets) == 1
        assert targets[0]["mva"] == "33333"

    def test_invalid_type_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            self._run(tmp_path, "mva,Type,location,action\n44444,Tires,,\n")

    def test_glass_missing_location_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            self._run(tmp_path, "mva,Type,location,action\n55555,Glass,,Replace\n")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv\Scripts\python.exe -m pytest tests/test_create_workitem_csv.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'WorkItems'`

- [ ] **Step 3: Create WorkItems/create_workitem.py**

Create `WorkItems/create_workitem.py` with the following content (based on root `create_workitem.py` with all changes applied):

```python
# WorkItems/create_workitem.py — Batch work item creation with persistent session
#
# Usage:
#   Create work items from CSV in a single session:
#     .venv\Scripts\python.exe WorkItems\create_workitem.py --csv WorkItems\create_workitem.csv
#
#   Create single MVA (Glass only):
#     .venv\Scripts\python.exe WorkItems\create_workitem.py 59257306
#

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import sys
from pathlib import Path

# Allow imports from repo root (playwright_prototype, utils, config packages)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.logger import log

VALID_GLASS_LOCATIONS = {
    "WS", "WINDSHIELD", "FRONT",
    "FLD", "FRD", "RLD", "RRD",
    "FLV", "FRV",
    "BW",
    "SR",
    "RLQ", "RRQ", "FRW",
}

from playwright.async_api import async_playwright
from config.config_loader import get_config
from playwright_prototype.config import (
    resolve_edge_profile_directory,
    resolve_edge_user_data_dir,
    resolve_headless,
    resolve_initial_delay,
    resolve_step_delay,
)
from playwright_prototype.session import ensure_profile_context
from playwright_prototype.steps import (
    ExistingWorkItemError,
    check_existing_work_item,
    click_add_work_item,
    complete_mileage_dialog,
    confirm_completion,
    create_work_item,
    handle_complaint_dialog,
    navigate_to_mva as pw_navigate_to_mva,
    select_opcode,
    warmup_compass as pw_warmup_compass,
)


def _resolve_row_work_item_action(row: dict, default_action: str) -> str:
    if "action" in row and row["action"].strip():
        action = row["action"].strip()
        if action.lower() in ["replace", "repair"]:
            return action.lower().capitalize()
    return default_action


def _build_create_targets(args) -> list[dict]:
    """Build list of (mva, type, location, action) targets from CLI args."""
    targets = []

    if args.csv:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            log.error("[CREATE] CSV file not found: %s", csv_path)
            sys.exit(1)

        valid_types = get_config("valid_complaint_types", ["Glass", "PM"])

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(line for line in f if not line.startswith("#"))
            if not reader.fieldnames or "mva" not in reader.fieldnames:
                log.error("[CREATE] CSV missing required 'mva' column")
                sys.exit(1)

            default_action = args.action or "Replace"
            for i, row in enumerate(reader, start=2):
                mva = (row.get("mva") or "").strip()
                if not mva:
                    log.warning("[CREATE] Row %d: blank mva — skipping", i)
                    continue

                work_type = (row.get("Type") or "Glass").strip()
                if work_type not in valid_types:
                    log.error(
                        "[CREATE] Row %d: invalid Type '%s' for MVA %s — must be one of: %s",
                        i, work_type, mva, ", ".join(valid_types),
                    )
                    sys.exit(1)

                if work_type == "Glass":
                    location = (row.get("location") or "").strip()
                    if not location:
                        log.error("[CREATE] Row %d: Glass row for MVA %s is missing location", i, mva)
                        sys.exit(1)
                    if location.upper() not in VALID_GLASS_LOCATIONS:
                        log.error(
                            "[CREATE] Row %d: invalid location '%s' for MVA %s — "
                            "must be a glass area code (e.g. WS, BW, FLD).",
                            i, location, mva,
                        )
                        sys.exit(1)
                    action = _resolve_row_work_item_action(row, default_action)
                else:
                    location = ""
                    action = ""

                targets.append({
                    "mva": mva,
                    "type": work_type,
                    "location": location,
                    "action": action,
                })

        log.info("[CREATE] Loaded %d MVA(s) from %s", len(targets), csv_path)
    else:
        targets.append({
            "mva": args.mva,
            "type": "Glass",
            "location": args.location or "WS",
            "action": args.action or "Replace",
        })

    return targets


async def process_mva(page, mva: str, type: str, location: str, action: str, step_delay_ms: int = 0) -> None:
    """Run the full work-item creation flow for a single MVA."""
    async def delay():
        if step_delay_ms:
            await page.wait_for_timeout(step_delay_ms)

    await navigate_to_mva(page, mva);                                                    await delay()
    await check_existing_work_item(page, mva, type);                                     await delay()
    await click_add_work_item(page, mva);                                                await delay()
    await handle_complaint_dialog(page, mva, type, location, action, step_delay_ms);     await delay()
    await complete_mileage_dialog(page, mva);                                            await delay()
    await select_opcode(page, type);                                                     await delay()
    await create_work_item(page);                                                        await delay()
    await confirm_completion(page)


async def _run_playwright_creation_async(targets: list[dict]) -> None:
    """Create multiple work items in a single persistent session."""
    headless = resolve_headless()
    edge_user_data_dir = resolve_edge_user_data_dir()
    edge_profile_directory = resolve_edge_profile_directory()
    step_delay_ms = resolve_step_delay()

    log.info("[CREATE] %s", "=" * 50)
    log.info("[CREATE] Work item creation - %d MVA(s)", len(targets))
    log.info("[CREATE] Backend: playwright")
    log.info("[CREATE] Profile: %s", edge_profile_directory)
    log.info("[CREATE] %s", "=" * 50)

    created_count = 0
    skipped_count = 0
    failed_count = 0

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(edge_user_data_dir),
            channel="msedge",
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                f"--profile-directory={edge_profile_directory}",
                "--start-maximized",
            ],
            no_viewport=True,
        )

        try:
            _, page = await ensure_profile_context(context)

            initial_delay_ms = resolve_initial_delay()
            if initial_delay_ms > 0:
                await page.wait_for_timeout(initial_delay_ms)

            log.info("[CREATE] Warming up Compass with dummy MVA 50227203...")
            await pw_warmup_compass(page)
            log.info("[CREATE] Compass warm-up complete")

            for target in targets:
                mva = target["mva"]
                work_type = target["type"]
                location = target["location"]
                action = target["action"]

                try:
                    log.info(
                        "[CREATE] Processing MVA %s (type=%s location=%s action=%s)...",
                        mva, work_type, location, action,
                    )
                    try:
                        await process_mva(page, mva, type=work_type, location=location,
                                          action=action, step_delay_ms=step_delay_ms)
                    except ExistingWorkItemError:
                        log.info("[CREATE] %s — SKIP: existing %s work item found", mva, work_type)
                        skipped_count += 1
                        continue

                    log.info("[CREATE] %s — Created", mva)
                    created_count += 1

                except Exception as e:
                    log.error("[CREATE] %s — FAILED: %s", mva, str(e))
                    failed_count += 1
                    continue

            await context.close()
            log.info("[CREATE] Browser closed.")

        except Exception as e:
            log.error("[CREATE] Session error: %s", str(e))
            await context.close()
            sys.exit(1)

    log.info("[CREATE] %s", "=" * 50)
    log.info("[CREATE] CREATION SUMMARY - %d MVA(s)", len(targets))
    log.info("[CREATE]   Created:  %d", created_count)
    log.info("[CREATE]   Skipped:  %d", skipped_count)
    log.info("[CREATE]   Failed:   %d", failed_count)
    log.info("[CREATE] %s", "=" * 50)

    if failed_count > 0 or (created_count == 0 and skipped_count == 0):
        sys.exit(1)


def _selenium_create(targets: list[dict]) -> None:
    log.error("[CREATE] Selenium backend for batch create not yet implemented")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Create work items in batch with persistent session"
    )
    parser.add_argument("mva", nargs="?", help="Single MVA to create (omit if using --csv)")
    parser.add_argument("--csv", help="CSV file with columns: mva,Type,location,action")
    parser.add_argument("--location", default="WS", help="Location code for single-MVA mode (default: WS)")
    parser.add_argument("--action", choices=["Replace", "Repair"], help="Action for single-MVA Glass mode")
    parser.add_argument(
        "--backend",
        choices=["selenium", "playwright"],
        default="playwright",
        help="Browser backend — default: playwright",
    )

    args = parser.parse_args()

    if not args.mva and not args.csv:
        parser.error("Either provide MVA or use --csv")
    if args.mva and args.csv:
        parser.error("Cannot use both MVA and --csv together")

    targets = _build_create_targets(args)

    if not targets:
        log.error("[CREATE] No targets to process")
        sys.exit(1)

    if args.backend == "playwright":
        asyncio.run(_run_playwright_creation_async(targets))
    else:
        _selenium_create(targets)


if __name__ == "__main__":
    main()
```

Also create `WorkItems/__init__.py` (empty, makes WorkItems a package so tests can import it):

```python
```

- [ ] **Step 4: Run CSV tests**

```bash
.venv\Scripts\python.exe -m pytest tests/test_create_workitem_csv.py -v
```

Expected: All PASS

- [ ] **Step 5: Run full test suite**

```bash
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add "WorkItems/create_workitem.py" "WorkItems/__init__.py" tests/test_create_workitem_csv.py
git commit -m "feat: add WorkItems/create_workitem.py with Type column and PM routing"
```

---

## Task 7: Create WorkItems/close_workitem.py

**Files:**
- Create: `WorkItems/close_workitem.py` (from root `close_workitem.py` with changes)

Changes from root version:
1. Add `sys.path` fix at top
2. Remove local `_GLASS_PATTERN`, `_PM_PATTERN`, `COMPLAINT_TYPE_PATTERNS` definitions
3. Import `COMPLAINT_TYPE_PATTERNS` from `playwright_prototype.steps`
4. Update fallback in `_playwright_close_work_item` from `_GLASS_PATTERN` to `COMPLAINT_TYPE_PATTERNS["Glass"]`
5. Add `#` comment-line skipping to `_load_csv`

- [ ] **Step 1: Write a failing test for comment-line skipping in close_workitem**

Add to a new test file `tests/test_close_workitem_csv.py`:

```python
"""Tests for _load_csv comment-line skipping in WorkItems/close_workitem.py."""
from pathlib import Path
import pytest


def _write_csv(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "test.csv"
    p.write_text(content, encoding="utf-8")
    return p


class TestLoadCsvCommentSkipping:

    def test_comment_lines_skipped(self, tmp_path):
        from WorkItems.close_workitem import _load_csv
        csv_path = _write_csv(
            tmp_path,
            "# header comment\nmva,Type\n# row comment\n11111,Glass\n",
        )
        rows = _load_csv(str(csv_path))
        assert len(rows) == 1
        assert rows[0]["mva"] == "11111"

    def test_blank_mva_skipped(self, tmp_path):
        from WorkItems.close_workitem import _load_csv
        csv_path = _write_csv(tmp_path, "mva,Type\n,Glass\n22222,PM\n")
        rows = _load_csv(str(csv_path))
        assert len(rows) == 1
        assert rows[0]["mva"] == "22222"

    def test_complaint_type_patterns_imported_from_steps(self):
        from WorkItems.close_workitem import COMPLAINT_TYPE_PATTERNS
        from playwright_prototype.steps import COMPLAINT_TYPE_PATTERNS as steps_patterns
        assert COMPLAINT_TYPE_PATTERNS is steps_patterns
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv\Scripts\python.exe -m pytest tests/test_close_workitem_csv.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Create WorkItems/close_workitem.py**

Create `WorkItems/close_workitem.py`. This is the root `close_workitem.py` with the following changes applied:

**At the very top** (before any other imports), add:
```python
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

**Remove** these three lines from the root-level definitions:
```python
_GLASS_PATTERN = re.compile(r"glass|windshield|crack|chip|window", re.I)
_PM_PATTERN = re.compile(r"PM", re.I)

COMPLAINT_TYPE_PATTERNS = {
    "Glass": _GLASS_PATTERN,
    "PM": _PM_PATTERN,
}
```

**Add** this import alongside the other `playwright_prototype.steps` imports:
```python
from playwright_prototype.steps import COMPLAINT_TYPE_PATTERNS
```

**In `_playwright_close_work_item`**, replace:
```python
pattern = COMPLAINT_TYPE_PATTERNS.get(complaint_type, _GLASS_PATTERN)
```
with:
```python
pattern = COMPLAINT_TYPE_PATTERNS.get(complaint_type, COMPLAINT_TYPE_PATTERNS["Glass"])
```

**In `_load_csv`**, replace:
```python
with open(path, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
```
with:
```python
with open(path, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(line for line in f if not line.startswith("#"))
```

- [ ] **Step 4: Run tests**

```bash
.venv\Scripts\python.exe -m pytest tests/test_close_workitem_csv.py -v
```

Expected: All PASS

- [ ] **Step 5: Run full test suite**

```bash
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add "WorkItems/close_workitem.py" tests/test_close_workitem_csv.py
git commit -m "feat: add WorkItems/close_workitem.py — import COMPLAINT_TYPE_PATTERNS from steps, comment-line skipping"
```

---

## Task 8: Create WorkItems/verify_workitem.py

**Files:**
- Create: `WorkItems/verify_workitem.py` (from root `verify_workitem.py` with sys.path fix only)

- [ ] **Step 1: Create WorkItems/verify_workitem.py**

Copy root `verify_workitem.py` verbatim, then insert at the very top (before `from __future__ import annotations`):

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

The final file begins:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from __future__ import annotations
...
```

> Note: `from __future__ import annotations` must remain the first statement after sys.path manipulation. Actually `from __future__` must be the very first statement in the file (after docstrings/comments). Put the sys.path block after `from __future__ import annotations` and before other imports:

```python
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import asyncio
...
```

- [ ] **Step 2: Verify the file imports cleanly**

```bash
.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'WorkItems'); import verify_workitem; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run full test suite**

```bash
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add "WorkItems/verify_workitem.py"
git commit -m "feat: add WorkItems/verify_workitem.py (move only + sys.path fix)"
```

---

## Task 9: Archive smoke_test_workitem.py; deprecate playwright_prototype/main.py

**Files:**
- Create: `archive/` (directory)
- Move: `smoke_test_workitem.py` → `archive/smoke_test_workitem.py`
- Modify: `playwright_prototype/main.py` (deprecation comment — already has the import update from Task 5)

- [ ] **Step 1: Create archive/ and move smoke_test_workitem.py**

```powershell
New-Item -ItemType Directory -Path "archive" -ErrorAction SilentlyContinue
Move-Item "smoke_test_workitem.py" "archive\smoke_test_workitem.py"
```

- [ ] **Step 2: Add deprecation comment to top of playwright_prototype/main.py**

The imports block already has the deprecation comment from Task 5. Verify it reads:
```python
# DEPRECATED: this prototype is superseded by WorkItems/create_workitem.py
# Do not add new features here. Remove once WorkItems/ is confirmed stable.
```

If the comment is missing (Task 5 not yet merged), add it now.

- [ ] **Step 3: Run full test suite**

```bash
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add archive/smoke_test_workitem.py playwright_prototype/main.py
git commit -m "chore: archive smoke_test_workitem.py; mark playwright_prototype/main.py deprecated"
```

---

## Task 10: Update CMD files

**Files:**
- Modify: `Run-CreateWorkItems.cmd`
- Modify: `Run-CloseWorkItems.cmd`
- Modify: `Run-VerifyWorkItems.cmd`
- Modify: `Run-SmokeWorkItems.cmd`

For each CMD, two changes: script path and default CSV path.

- [ ] **Step 1: Update Run-CreateWorkItems.cmd**

Change:
```batch
set "CSV_PATH=playwright_prototype\sample_mvas.csv"
```
to:
```batch
set "CSV_PATH=WorkItems\create_workitem.csv"
```

Change:
```batch
"%VENV_PY%" create_workitem.py --csv "%CSV_PATH%" --backend playwright
```
to:
```batch
"%VENV_PY%" WorkItems\create_workitem.py --csv "%CSV_PATH%" --backend playwright
```

Also update the usage comment block from:
```batch
rem  CSV format: mva,location,action
```
to:
```batch
rem  CSV format: mva,Type,location,action
rem    Type: Glass or PM (defaults to Glass if omitted)
rem    location required for Glass rows (e.g. WS, BW, FLD)
rem    action required when Type=Glass and location=WS (Replace or Repair)
```

- [ ] **Step 2: Update Run-CloseWorkItems.cmd**

Change:
```batch
set "CSV_PATH=playwright_prototype\sample_mvas.csv"
```
to:
```batch
set "CSV_PATH=WorkItems\close_workitem.csv"
```

Change:
```batch
"%VENV_PY%" close_workitem.py --csv "%CSV_PATH%" --no-pause
```
to:
```batch
"%VENV_PY%" WorkItems\close_workitem.py --csv "%CSV_PATH%" --no-pause
```

- [ ] **Step 3: Update Run-VerifyWorkItems.cmd**

Change:
```batch
set "CSV_PATH=playwright_prototype\sample_mvas.csv"
```
to:
```batch
set "CSV_PATH=WorkItems\create_workitem.csv"
```

Change:
```batch
"%VENV_PY%" verify_workitem.py --csv "%CSV_PATH%" --type "%TYPE_FILTER%" --no-pause
```
to:
```batch
"%VENV_PY%" WorkItems\verify_workitem.py --csv "%CSV_PATH%" --type "%TYPE_FILTER%" --no-pause
```

- [ ] **Step 4: Update Run-SmokeWorkItems.cmd**

Change:
```batch
set "CSV_PATH=playwright_prototype\sample_mvas.csv"
```
to:
```batch
set "CSV_PATH=WorkItems\create_workitem.csv"
```

Change:
```batch
"%VENV_PY%" create_workitem.py --csv "%CSV_PATH%" %CREATE_FLAG%
```
to:
```batch
"%VENV_PY%" WorkItems\create_workitem.py --csv "%CSV_PATH%" %CREATE_FLAG%
```

- [ ] **Step 5: Verify CSV file exists before testing CMD syntax**

```powershell
Test-Path "WorkItems\create_workitem.csv"
Test-Path "WorkItems\close_workitem.csv"
```

Expected: both `True`

- [ ] **Step 6: Run full test suite one final time**

```bash
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add Run-CreateWorkItems.cmd Run-CloseWorkItems.cmd Run-VerifyWorkItems.cmd Run-SmokeWorkItems.cmd
git commit -m "feat: update CMD launchers to WorkItems/ paths"
```

---

## Task 11: PM trial run with --pause

This task verifies the PM branch in the actual Compass UI. The `--pause` flag steps through each action with Playwright Inspector pauses.

> `WorkItems/create_workitem.py` does not yet have a `--pause` flag (that was in the deprecated `playwright_prototype/main.py`). Use the `STEP_DELAY_MS` env variable or add `--pause` support first if needed. For initial trial, rely on slow step delays and visual inspection.

- [ ] **Step 1: Add a PM row to WorkItems/create_workitem.csv**

Edit `WorkItems/create_workitem.csv` to add a real PM MVA for the trial:
```
mva,Type,location,action
<pm_mva_here>,PM,,
```

- [ ] **Step 2: Run with slow delays to observe each step**

Set a step delay so each action is visible:
```powershell
$env:GLASS_STEP_DELAY_MS = "3000"
.venv\Scripts\python.exe WorkItems\create_workitem.py --csv WorkItems\create_workitem.csv
```

- [ ] **Step 3: Verify known unknown — Additional Info checkbox**

Observe the Additional Info screen on first trial run:
- If the checkbox appears unchecked by default: no code change needed, the current implementation is correct.
- If the checkbox appears checked by default: add an explicit uncheck step in `handle_complaint_dialog` PM branch, before `_click_submit_complaint`:

```python
# Only needed if checkbox is checked by default:
checkbox = page.locator('input[type="checkbox"]').first
if await checkbox.is_checked():
    await checkbox.uncheck()
    log.info("[STEPS] %s PM: unchecked Additional Info checkbox", mva)
```

- [ ] **Step 4: Commit any checkbox fix if needed**

```bash
git add playwright_prototype/steps.py
git commit -m "fix: uncheck Additional Info checkbox for PM if checked by default"
```

---

## Self-Review Checklist

Spec coverage:

| Spec requirement | Task |
|-----------------|------|
| WorkItems/ folder with script/csv/log naming | Task 1, 6, 7, 8 |
| Unified CSV schema mva,Type,location,action | Task 1, 6 |
| Type validation (Glass/PM, error-exit on invalid) | Task 6 |
| Glass requires location; WS requires action | Task 6 |
| PM leaves location/action blank | Task 6 |
| Comment-line (#) skipping in both scripts | Task 6, 7 |
| COMPLAINT_TYPE_PATTERNS moved to steps.py | Task 3 |
| check_existing_work_item(page, mva, type) | Task 3 |
| handle_complaint_dialog PM branch | Task 4 |
| select_opcode(page, type) | Task 3 |
| pm_opcode config key | Task 2 |
| CMD file path updates | Task 10 |
| smoke_test_workitem.py archived | Task 9 |
| playwright_prototype/main.py deprecated | Task 5, 9 |
| verify_workitem.py moved (no functional change) | Task 8 |
| PM trial --pause run | Task 11 |
