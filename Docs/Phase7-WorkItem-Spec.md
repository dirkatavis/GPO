# GPO Phase 7 — Compass Work Item Creation
## Technical Specification & Execution Runbook

> **How to use this document:**
> Save as `Docs/Phase7-WorkItem-Spec.md` in the repo.
> Start Claude Code with:
> ```
> Read Docs/Phase7-WorkItem-Spec.md and execute it exactly. Start at Step 0.
> ```

---

## Mission

Two deliverables ship together in this branch:

1. **Refactor `WorkItemHandler`** into a clean, truly generic plugin interface —
   the authoritative pattern for all future work item types (PM, Brake, etc.)
2. **Build Phase 7** — a standalone script that reads from the `GlassClaims` Google Sheet
   and creates Compass work items for eligible MVAs

These ship together because Phase 7 is the first real consumer of the refactored handler.
The refactor proves itself by powering the feature.

**Design principle:** This codebase is one of several narrowly focused repos moving toward
a single unified automation platform. Every interface and contract designed here should be
portable. Keep GPO-specific logic in GPO-specific files, but design the seams to move.

---

## Branching Strategy

This feature is delivered as a sequential chain of branches — one per spec phase.
Each branch is based on the previous one. Each phase gets its own PR.
Never branch off `main` directly (except the first). Never skip a phase.

```
main
└── feature/phase7-a-handler-refactor     ← Phase A (COMPLETE ✓)
    └── feature/phase7-b-core             ← Phase B (next)
        └── feature/phase7-c-entry-point  ← Phase C
            └── feature/phase7-d-e2e      ← Phase D
                └── feature/phase7-e-docs ← Phase E (merges to main)
```

**PR target for each branch is its parent branch, not main.**
Only Phase E's PR targets main — that is the full feature merge.

---

## Phase Completion Log

### Phase A — COMPLETE ✓ (2026-04-11)

**Branch:** `feature/phase7-a-handler-refactor` | **PR:** #12

**Test counts:** 116 passed, 2 skipped (live-credential integration guards)

**Deliverables completed:**
- `flows/complaints_flows.py` — `detect_existing_complaints()` renamed to `detect_pm_complaints()`; `detect_glass_complaints()` added with dynamic-suffix-safe partial-class selector; keyword list: `["glass", "windshield", "crack", "chip", "window"]`
- `flows/work_item_handler.py` — abstract `detect_complaints()` added to base class; `_handle_complaint_flow()` now fully handler-agnostic; `GlassWorkItemHandler` implements `detect_complaints()` with `self._current_mva` forwarded; `_current_mva = None` default in `__init__`
- `core/eligibility.py` — new module; `is_notification_eligible()` supports both `"Damage Type"` and `"damage_type"` key formats; `"Damage Type"` takes precedence when both present
- `GlassOrchestrator.py` — Phase 6 notify now filters through `is_notification_eligible()` (Repair rows excluded)
- `src/GlassDamageWorkItemScript.py` — all 7 hardcoded Compass hash-suffixed class names replaced with partial-class CSS selectors
- `tests/test_work_item_handler.py` — new (30 tests)
- `tests/test_eligibility.py` — new (18 tests)

**Implementation decisions:**
- Keyword `"replace"` removed from both `detect_glass_complaints()` and `should_handle_existing_complaint()` — too broad, matched "brake pad replacement". Replaced with `"window"` to cover "Side Window Damage" tiles.
- `is_notification_eligible()` placed in `core/eligibility.py` (not inline in `GlassOrchestrator.py`) for clean import by both Phase 6 and Phase 7.

---

### Phase B — COMPLETE ✓ (2026-04-12)

**Branch:** `feature/phase7-b-core` | **PR:** #13

**Test counts:** 143 passed, 2 skipped (unit + integration, E2E excluded)

**Deliverables completed:**
- `flows/work_item_flow.py` — `check_existing_work_item(driver, mva, work_item_type="GLASS")` added; uses existing `get_work_items()` (open items only); explicit type dispatch for future extensibility; returns `False` on any exception
- `flows/glass_work_item_phase.py` — new module; `read_glass_claims()` reads GlassClaims sheet, filters by `is_notification_eligible()` and blank `WorkItemCreated`; `run_glass_work_item_phase()` loops all MVAs, never aborts, returns `{processed, created, skipped, failed}`; `GlassClaimsUpdater` class caches headers + MVA→row map and writes `WorkItemCreated=Y` on success
- `GlassWorkItems.py` — standalone operator entry point; login → sheet connect → manifest → phase run → summary log; driver in `try/finally`
- `Run-GlassWorkItems.cmd` — bootstraps venv, syncs requirements (SHA256 stamp), launches `GlassWorkItems.py`; matches `Run-GlassOrchestrator.cmd` pattern
- `tests/test_glass_work_item_phase.py` — new (22 tests)
- `tests/test_integration.py` — IT-6 integration tests added (132 lines)

**Implementation decisions:**
- `GlassClaimsUpdater` caches the `WorkItemCreated` column index and MVA→row map on first use to avoid O(n²) sheet reads on large manifests
- `Location` column in sheet defaults to `"WINDSHIELD"` when blank — matches confirmed design decision that all current Replacement items are windshield
- Complete new complaint workflow wired end-to-end: mileage dialog → OpCode selection → finalize work item

---

### Phase C — COMPLETE ✓ (2026-04-12)

**Branch:** `feature/phase7-c-entry-point` | **PR:** #14

**Test counts:** 143 passed, 2 skipped

**Deliverables completed:**
- `tests/test_integration.py` — IT-6 integration suite for `run_glass_work_item_phase()`: full orchestration path, two-MVA mixed manifest, exception isolation, `WorkItemCreated` sheet update verified

**Implementation decisions:**
- Unused `WorkItemConfig` import removed from IT-6 test after review

---

### Phase D — COMPLETE ✓ (2026-04-13)

**Branch:** `feature/phase7-d-e2e` | **PR:** pending

**Test counts:** 143 unit/integration passed, 2 skipped; 7 E2E scenarios written; real-world validation passed against live Compass on 2026-04-13

**Deliverables completed:**
- `tests/test_e2e_glass_work_item.py` — 7 E2E scenarios tagged `@pytest.mark.e2e`: skip existing work item, create windshield (new complaint), create with existing complaint association, side glass, rear glass, mixed 3-MVA manifest, idempotency (second run skips)
- `pytest.ini` — `e2e` marker registered; opt-in via `GLASS_RUN_E2E_TESTS=1`; per-scenario MVA env vars documented in file header

**Implementation decisions:**
- E2E opt-in guard (`GLASS_RUN_E2E_TESTS=1`) prevents accidental live-Compass runs in CI
- Real-world validation against today's production glass damage confirmed correct behavior in lieu of full scripted E2E scenario run

---

## Step 0 — Determine Current Phase and Branch

Before reading any files or writing any code, run:

```bash
git branch        # see current branch
git log --oneline -5   # confirm what's already done
```

Then follow the correct step for where you are:

### If starting Phase A (first run):
```bash
git checkout -b feature/phase7-a-handler-refactor
git branch   # confirm
claude --dangerously-skip-permissions
```

### If starting Phase B:
```bash
git checkout feature/phase7-a-handler-refactor
git pull
git checkout -b feature/phase7-b-core
git branch   # confirm
claude --dangerously-skip-permissions
```

### If starting Phase C:
```bash
git checkout feature/phase7-b-core
git pull
git checkout -b feature/phase7-c-entry-point
git branch   # confirm
claude --dangerously-skip-permissions
```

### If starting Phase D:
```bash
git checkout feature/phase7-c-entry-point
git pull
git checkout -b feature/phase7-d-e2e
git branch   # confirm
claude --dangerously-skip-permissions
```

### If starting Phase E:
```bash
git checkout feature/phase7-d-e2e
git pull
git checkout -b feature/phase7-e-docs
git branch   # confirm
claude --dangerously-skip-permissions
```

**Do not make any changes until the correct branch is active and confirmed.**

---

## Read First — Before Touching Any Code

Read all of these in full before writing a single line:

- `CLAUDE.md` — project overview, FRA profile, gotchas
- `README.md` — 6-phase architecture and data contract
- `src/GlassDamageWorkItemScript.py` — existing Phase 7 attempt; extend or replace,
  your call, but do not lose any working functionality
- `flows/work_item_handler.py` — the ABC and `GlassWorkItemHandler` you are refactoring
- `flows/complaints_flows.py` — complaint flows; some need restructuring (see Part 1)
- `flows/work_item_flow.py` — existing work item navigation flows
- `pages/work_items_tab.py` — work items tab page object
- `core/complaint_types.py` — enums; treat as read-only
- `utils/ui_helpers.py` — `click_element()`, `find_element()` — use exclusively
- `utils/logger.py` — all logging goes through here, no `print()`
- `Docs/GlassDamageWorkItemRequirements.md` — current requirements
- `tests/` — all test files; you will update and add tests
- `GlassOrchestrator.py` — locate Phase 6 Replacement filter logic (see Part 3)

---

## Selector Rules — Non-Negotiable

Compass (fleet-operations-pwa) generates class names with runtime suffixes:

    fleet-operations-pwa__complaintItem__qeei1l
                                          ↑ dynamic — never use this

**Always match the stable prefix only:**
- XPath: `contains(@class, "fleet-operations-pwa__complaintItem")`
- CSS: `[class*="fleet-operations-pwa__complaintItem"]`

Every new selector must follow this pattern. Model after existing selectors in
`complaints_flows.py` and `pages/`. No exceptions.

---

## Confirmed Design Decisions

These are resolved. Do not reopen them.

### Glass Location
The current pipeline does not carry a glass location field. All Replacement items today
are windshield — side and rear damage is rare and handled manually by the operator outside
this script. This is a **known limitation**, not a gap to fill.

- Default `location = "WINDSHIELD"` for all rows — this is correct behavior, not a fallback
- Add a `Location` column to `GlassClaims` sheet for future operator input (Windshield / Side / Rear)
- Phase 7 reads `Location` from the sheet — if blank, defaults to `"WINDSHIELD"`
- Document this limitation clearly in the spec and in code comments

### Work Item Search Scope
There is always at most **one open work item per type** per vehicle. Multiple closed/historical
items may exist — ignore them. `check_existing_work_item()` filters to open/active only,
matches on type, returns `True` on first match.

### Replacement-Only Filter
Phase 7 processes Replacement items only — same as Phase 6. Extract the existing Phase 6
filter into a shared `is_notification_eligible(row) -> bool` helper. Both Phase 6 and
Phase 7 call it. This touches production code — add a Phase 6 regression test to prove
behavior is unchanged.

### Phase 7 is Standalone — Sheet is the Data Source
Phase 7 is **not** wired into `GlassOrchestrator.py`. It is a separate manual step:

1. Operator runs Phase 1–6 (normal pipeline)
2. Operator fills in `Location` column on `GlassClaims` sheet (if needed)
3. Operator runs Phase 7 script

Phase 7 reads directly from the `GlassClaims` sheet. It needs an **idempotency column**
`WorkItemCreated` (blank / `Y` / timestamp) so re-runs safely skip already-processed rows.

### Driver Lifecycle
Phase 7 owns its own Selenium driver. Initialize with `create_driver()` / `get_driver()`
(match pattern in `GlassDataParser.py`). Always call `quit_driver()` in a `try/finally`
block — the driver must quit even if the script fails.

---

## Part 1 — Refactor `WorkItemHandler` to a Clean Plugin Interface

### Problems in the Current Implementation

1. `_handle_complaint_flow()` in the **base class** calls `detect_existing_complaints()`
   which filters for `"PM"` tiles — wrong for glass, wrong for every future type
2. `detect_existing_complaints()` is named generically but implements PM-specific logic
3. `should_handle_existing_complaint()` is abstract but never actually used by the base
   class to filter — the delegation is incomplete
4. Factory has commented-out PM/Brake stubs — misleading noise

### Fix: `flows/complaints_flows.py`

- Rename `detect_existing_complaints()` → `detect_pm_complaints()` — honest naming
- Update all call sites
- Add alongside it:
  ```python
  def detect_glass_complaints(driver, mva: str) -> list:
  ```
  Filters tiles for glass keywords: `["glass", "windshield", "crack", "chip", "replace"]`
- Both use the dynamic-suffix-safe selector pattern
- Neither is called by the base class — they are subclass implementation details

### Fix: `flows/work_item_handler.py` — Base Class

- Add new abstract method:
  ```python
  @abstractmethod
  def detect_complaints(self, driver) -> list:
      """Return complaint tile elements relevant to this work item type."""
      pass
  ```
- Update `_handle_complaint_flow()` to call `self.detect_complaints(driver)`
- Base class drives the filter loop using `self.should_handle_existing_complaint(tile.text)`
- Base class never imports or references any specific complaint detection function

### Fix: `flows/work_item_handler.py` — `GlassWorkItemHandler`

- Implement `detect_complaints()`:
  ```python
  def detect_complaints(self, driver) -> list:
      from flows.complaints_flows import detect_glass_complaints
      return detect_glass_complaints(driver, self._current_mva)
  ```
- Store `config.mva` as `self._current_mva` at the start of `create_work_item()` so
  subclass methods can reference it without threading `mva` through every call
- Clean up any logic that duplicates what the base class now handles

### Fix: Factory

Replace commented-out stubs with:
```python
# To add a new work item type:
# 1. Subclass WorkItemHandler
# 2. Implement: detect_complaints, should_handle_existing_complaint,
#    create_new_complaint, handle_existing_complaint
# 3. Register the type string here
```
Keep the `ValueError` for unknown types.

---

## Part 2 — Extract `is_notification_eligible()` from Phase 6

Locate the Replacement filter in `GlassOrchestrator.py` Phase 6. Extract it to
`core/eligibility.py` (new file):

```python
def is_notification_eligible(row: dict) -> bool:
    """Return True if this row should trigger notification and work item creation."""
    return row.get("damage_type", "Replacement").strip().title() == "Replacement"
```

Update Phase 6 in `GlassOrchestrator.py` to call `is_notification_eligible()`.
Add a Phase 6 regression test to `tests/test_unit.py` confirming behavior is unchanged.

---

## Part 3 — Add `check_existing_work_item()` to `flows/work_item_flow.py`

```python
def check_existing_work_item(driver, mva: str, work_item_type: str = "GLASS") -> bool:
```

- Navigate to the work items tab for the MVA using existing page objects
- Filter to **open/active** items only
- Match on `work_item_type` — return `True` on first open match
- Only `"GLASS"` implemented now — use explicit type dispatch so future types slot in
- Log with `[WORKITEM]` prefix
- On any exception: log, return `False`, do not raise

---

## Part 4 — Build Phase 7 Script

### `flows/glass_work_item_phase.py`

New file. Add header:

```python
# Phase 7 — Compass Work Item Creation
# Standalone script — not part of the main GlassOrchestrator pipeline.
# Reads from GlassClaims sheet, creates Compass work items for eligible MVAs.
#
# KNOWN LIMITATION: Location defaults to WINDSHIELD for all rows.
# Side/rear damage is rare and handled manually by the operator.
# When Orca scan data includes location, update read_glass_claims() to parse it.
#
# ARCHITECTURE NOTE: Designed for extraction into the unified automation repo.
# Manifest contract (list of plain dicts) and return contract (summary dict) are portable.
# WorkItemHandler subclasses are the extension point — not this orchestrator.
```

#### Sheet Reader

```python
def read_glass_claims(sheet_client, tab_name: str = "GlassClaims") -> list[dict]:
```

- Read all rows from `GlassClaims` tab
- Filter to `is_notification_eligible(row)` rows only
- Filter to rows where `WorkItemCreated` column is blank
- For each row, set `location = row.get("Location") or "WINDSHIELD"`
- Return list of plain dicts with keys: `mva`, `damage_type`, `location`

#### Phase Runner

```python
def run_glass_work_item_phase(driver, manifest: list[dict], sheet_client=None,
                               tab_name: str = "GlassClaims") -> dict:
```

For each entry:
1. Log `[PHASE7] {mva} - Starting work item review`
2. Call `check_existing_work_item(driver, mva, work_item_type="GLASS")`
3. If found: log and increment `skipped`
4. If not found: build `WorkItemConfig(mva, damage_type, location)`, call
   `create_work_item_handler("GLASS", driver).create_work_item(config)`
5. On success: mark `WorkItemCreated = Y` in sheet if `sheet_client` provided
6. On any exception: log `[PHASE7][ERROR] {mva} - {error}`, increment `failed`, continue
7. Return: `{"processed": n, "created": n, "skipped": n, "failed": n}`

**Never abort the loop.** All MVAs must be attempted regardless of prior failures.

### Entry Point: `GlassWorkItems.py` (new root-level script)

```python
# GlassWorkItems.py — Phase 7 standalone entry point
# Run after Phase 1-6 and after operator has reviewed/filled Location column.
```

- Login flow using existing `LoginFlow`
- Initialize driver with `create_driver()` / `get_driver()`
- Connect to Google Sheet using `Service_account.json`
- Call `read_glass_claims()` to build manifest
- Log manifest size before processing
- Call `run_glass_work_item_phase(driver, manifest, sheet_client)`
- Log summary dict on completion
- `quit_driver()` in `try/finally`

### Runner: `Run-GlassWorkItems.cmd` (new)

Match the pattern of `Run-GlassOrchestrator.cmd`:
- Bootstrap `.venv` if missing
- Install `requirements.txt`
- Launch `GlassWorkItems.py` with venv interpreter

---

## Part 5 — Update Google Sheet Schema

Add two columns to `GlassClaims` tab:

| Column | Values | Notes |
|---|---|---|
| `Location` | `Windshield` / `Side` / `Rear` / blank | Operator fills in; blank defaults to Windshield |
| `WorkItemCreated` | blank / `Y` / timestamp | Phase 7 writes this after successful creation |

Update Phase 5 in `GlassOrchestrator.py` to write the `Location` column header
(blank value — operator fills in). Do not change any Phase 5 data logic.

---

## Multi-Agent Execution Model

You are the **manager agent**. Delegate all work to sub-agents via the `Task` tool.
Never implement directly — coordinate, gate, and iterate.

### Agent Roles

**ImplementationAgent** — writes production code only, never tests
**TestAgent** — writes and runs all tests; TDD order: test first, confirm failure, then signal impl
**ReviewAgent** — line-level code review; returns specific issues with file/line/fix, never vague summaries
**DocsAgent** — updates documentation after all code is complete and reviewed

### Execution Phases

Each execution phase maps to a git branch. Complete the phase, then commit and push
before the next session starts.

#### Phase A — Refactor (Parts 1 & 2) — branch: `feature/phase7-a-handler-refactor`
**STATUS: COMPLETE ✓ — 116 tests passing**
1. TestAgent: write failing unit tests for the handler refactor and `is_notification_eligible()`
2. ImplementationAgent: implement Parts 1 and 2
3. TestAgent: run tests, report failures, iterate with ImplementationAgent until green
4. ReviewAgent: review diff, iterate until clean

#### Phase B — Phase 7 Core (Parts 3 & 4) — branch: `feature/phase7-b-core`
1. TestAgent: write failing unit tests for `check_existing_work_item()` and `run_glass_work_item_phase()`
2. ImplementationAgent: implement Parts 3 and 4
3. TestAgent: run full unit suite, iterate until green
4. ReviewAgent: review diff, iterate until clean
5. Commit and push before closing session

#### Phase C — Entry Point & Sheet Schema (Part 5) — branch: `feature/phase7-c-entry-point`
1. ImplementationAgent: implement `GlassWorkItems.py`, `Run-GlassWorkItems.cmd`, sheet schema (Part 5)
2. TestAgent: write and run integration tests (Layer 2 below)
3. ImplementationAgent: fix any failures
4. ReviewAgent: final review of complete diff — last gate before E2E
5. Commit and push before closing session

#### Phase D — E2E Against Real Compass — branch: `feature/phase7-d-e2e`
1. TestAgent: write E2E test file (Layer 3 below)
2. TestAgent: execute against live Compass:
   ```bash
   .venv\Scripts\python.exe -m pytest tests/test_e2e_glass_work_item.py -v -m e2e
   ```
3. ImplementationAgent: fix failures, iterate until all E2E scenarios pass
4. Commit and push before closing session

#### Phase E — Docs — branch: `feature/phase7-e-docs`
1. DocsAgent: update `Docs/GlassDamageWorkItemRequirements.md` with Phase 7 section
   and `WorkItemHandler` extension guide
2. Manager confirms docs are accurate against the final implementation
3. Commit and push, then execute Phase G chain merge

#### Phase G — Final Gate
Manager confirms before declaring branch merge-ready:
- `git diff feature/phase7-d-e2e` — all Phase E changes intentional
- `.venv\Scripts\python.exe -m pytest tests/ -v` — full suite green
- E2E tests green against real Compass
- ReviewAgent has no outstanding issues
- `WorkItemCreated` column written correctly on a real sheet run
- Docs updated

**Chain merge sequence to close out the full feature:**
```bash
# Merge each phase into its parent, bottom up
git checkout feature/phase7-d-e2e
git merge feature/phase7-e-docs
git push

git checkout feature/phase7-c-entry-point
git merge feature/phase7-d-e2e
git push

git checkout feature/phase7-b-core
git merge feature/phase7-c-entry-point
git push

git checkout feature/phase7-a-handler-refactor
git merge feature/phase7-b-core
git push

# Final PR on GitHub: feature/phase7-a-handler-refactor → main
# All checks must pass before merge — do not merge locally
```

Only open the final PR to `main` after the full chain is merged and all tests pass.

---

## Test Specifications

### Layer 1 — Unit Tests (no driver, no browser, no network)

TDD: write first, confirm failing, then implement.

**`tests/test_work_item_handler.py`** (new):
- `detect_complaints()` calls `detect_glass_complaints()`
- `should_handle_existing_complaint()` — True for glass keywords, False for unrelated
- `map_damage_type_to_ui()` all combinations:
  - REPAIR + WINDSHIELD → WINDSHIELD_CHIP
  - REPAIR + SIDE → SIDE_REAR_WINDOW_DAMAGE
  - REPAIR + REAR → SIDE_REAR_WINDOW_DAMAGE
  - REPAIR + None → SIDE_REAR_WINDOW_DAMAGE
  - REPLACEMENT + WINDSHIELD → WINDSHIELD_CRACK
  - REPLACEMENT + SIDE → SIDE_REAR_WINDOW_DAMAGE
  - REPLACEMENT + REAR → SIDE_REAR_WINDOW_DAMAGE
  - REPLACEMENT + None → UNKNOWN
  - None + None → UNKNOWN
- Factory: `"GLASS"` → `GlassWorkItemHandler`, `"UNKNOWN"` → `ValueError`
- `WorkItemConfig`: strips whitespace from `mva`, uppercases `damage_type` and `location`

**`tests/test_glass_work_item_phase.py`** (new):
- Empty manifest → `{"processed": 0, "created": 0, "skipped": 0, "failed": 0}`
- Skip path: `check_existing_work_item` mocked True → `skipped` incremented, handler never called
- Create path: mock returns False, handler returns `{"status": "created"}` → `created` incremented
- Failure isolation: first MVA raises → `failed` incremented, second MVA still processed
- Missing `damage_type` → defaults to `"Replacement"`, no raise
- Missing `location` → defaults to `"WINDSHIELD"`, no raise
- `is_notification_eligible()` filters Repair rows correctly
- Summary dict always has all four keys

**`tests/test_eligibility.py`** (new):
- Replacement → eligible
- Repair → not eligible
- Missing damage_type → eligible (defaults to Replacement)
- Case-insensitive match

**Update existing tests:**
- `detect_existing_complaints()` → `detect_pm_complaints()` at all call sites
- `_handle_complaint_flow()` tests updated to reflect `detect_complaints()` delegation
- Phase 6 regression: behavior unchanged after `is_notification_eligible()` extraction

---

### Layer 2 — Integration Tests (driver mocked)

Add to `tests/test_integration.py`:
- Full path: `check_existing_work_item` False → `GlassWorkItemHandler.create_work_item()`
  called with correct `WorkItemConfig` (mva, damage_type, location all correct)
- Two-MVA manifest: one skips, one creates — both attempted, counts correct
- Exception in `create_work_item()` does not propagate out of `run_glass_work_item_phase()`
- `is_notification_eligible()` used consistently — Phase 6 and Phase 7 same behavior
- `WorkItemCreated` column updated in sheet mock after successful creation

---

### Layer 3 — E2E Tests (real Compass, real browser)

Tag all `@pytest.mark.e2e`. Add marker to `pytest.ini`:
```ini
[pytest]
markers =
    e2e: End-to-end tests requiring a live Compass instance and credentials
```

**`tests/test_e2e_glass_work_item.py`** (new):

1. **Skip — existing open work item:** Known MVA with active glass work item →
   `check_existing_work_item()` returns True, no new item created
2. **Create — Windshield, no existing complaint:** Clean test MVA, `location="WINDSHIELD"` →
   work item created, `Windshield Crack` complaint type confirmed in Compass
3. **Create — existing complaint association:** MVA with existing glass complaint →
   complaint associated, not recreated, work item created
4. **Create — Side glass:** `location="SIDE"` →
   `Side/Rear Window Damage` complaint type confirmed in Compass
5. **Create — Rear glass:** `location="REAR"` →
   `Side/Rear Window Damage` complaint type confirmed in Compass
6. **Mixed manifest (3 MVAs):** existing work item + clean + invalid →
   `skipped=1, created=1, failed=1, processed=3`
7. **Idempotency:** Run Phase 7 twice on same MVA →
   second run skips (WorkItemCreated already set), no duplicate created

---

## Code Style — Non-Negotiable

- Author/date/description block comment on every new function (match `work_item_handler.py` style)
- `[PHASE7]` log tag for all Phase 7 messages
- `[WORKITEM]`, `[GLASS]`, `[COMPLAINT]` tags unchanged on their modules
- `time.sleep()` for UI waits — match durations in adjacent flows
- No `print()` anywhere — only `log.*`
- Follow existing import ordering in each modified file

---

## Do Not Touch

- `GlassDataParser.py` or Phase 1–3 logic
- `core/complaint_types.py` — enums are complete
- Any `pages/` files — use existing page objects as-is
- `config/` files
- Phase 5 data logic — only add column headers, no data changes