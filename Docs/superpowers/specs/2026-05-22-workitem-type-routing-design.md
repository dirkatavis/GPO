# Work Item Type Routing — Design Spec
_Date: 2026-05-22_

## Goal

Generalize the work item scripts to support multiple work item types via a shared CSV schema,
and consolidate all user-facing scripts into a `WorkItems/` folder with consistent naming.
Initial types: **Glass** (existing, proven) and **PM** (new, to be trialled via `--pause`).

---

## Folder Structure

```
WorkItems/                        ← user-facing scripts, CSVs, logs
  create_workitem.py              ← moved from root
  close_workitem.py               ← moved from root
  verify_workitem.py              ← moved from root
  create_workitem.csv             ← was playwright_prototype/sample_mvas.csv
  close_workitem.csv              ← new (same schema, populated by user)
  create_workitem.log
  close_workitem.log
  verify_workitem.log

playwright_prototype/             ← shared support package — stays at root
  steps.py                        ← updated (see below)
  session.py
  config.py
  login.py
  profile_launch_check.py
  main.py                         ← deprecated in place (see below)

archive/
  smoke_test_workitem.py          ← moved here (Run-SmokeWorkItems.cmd calls create_workitem.py, not this)
```

### File disposition

| File | Action | Reason |
|---|---|---|
| `create_workitem.py` | Move to `WorkItems/` | Active — called by Run-CreateWorkItems.cmd, Run-SmokeWorkItems.cmd |
| `close_workitem.py` | Move to `WorkItems/` | Active — called by Run-CloseWorkItems.cmd |
| `verify_workitem.py` | Move to `WorkItems/` | Active — called by Run-VerifyWorkItems.cmd |
| `smoke_test_workitem.py` | Archive to `archive/` | Not called by any CMD; superseded by create_workitem.py |
| `playwright_prototype/main.py` | Deprecate in place | Original prototype; not called by any CMD; superseded by create_workitem.py. Add deprecation comment pointing to WorkItems/create_workitem.py. Remove once WorkItems/ confirmed stable. |
| `playwright_prototype/sample_mvas.csv` | Rename/move to `WorkItems/create_workitem.csv` | All CMD files currently default to this path; CMD files updated accordingly |

---

## CMD File Updates

All four launchers need their script path and default CSV path updated:

| CMD file | Script path change | CSV path change |
|---|---|---|
| `Run-CreateWorkItems.cmd` | `create_workitem.py` → `WorkItems\create_workitem.py` | `playwright_prototype\sample_mvas.csv` → `WorkItems\create_workitem.csv` |
| `Run-CloseWorkItems.cmd` | `close_workitem.py` → `WorkItems\close_workitem.py` | `playwright_prototype\sample_mvas.csv` → `WorkItems\close_workitem.csv` |
| `Run-VerifyWorkItems.cmd` | `verify_workitem.py` → `WorkItems\verify_workitem.py` | `playwright_prototype\sample_mvas.csv` → `WorkItems\create_workitem.csv` |
| `Run-SmokeWorkItems.cmd` | `create_workitem.py` → `WorkItems\create_workitem.py` | `playwright_prototype\sample_mvas.csv` → `WorkItems\create_workitem.csv` |

---

## Unified CSV Schema

Both `create_workitem.csv` and `close_workitem.csv` use the same format:

```
# create_workitem.csv — input for WorkItems/create_workitem.py
# (close_workitem.csv uses the same schema)
#
# Columns:
#   mva      — MVA number (required)
#   Type     — Work item type: Glass, PM               (required)
#   location — Glass only: WS, back, side              (required for Glass)
#   action   — Glass/WS only: Replace or Repair        (required when Type=Glass and location=WS)
#
# Notes:
#   - Repair is only valid for windshields (location=WS)
#   - back/side always map to Replacement regardless of action
#   - PM rows leave location and action blank
#   - Lines starting with # are ignored
#
mva,Type,location,action
61444283,Glass,WS,Replace
57503994,Glass,back,
61119446,PM,,
```

### Validation rules

| Column | Required? | Values | Rule |
|---|---|---|---|
| `mva` | Always | number | Blank rows skipped |
| `Type` | Always | `Glass`, `PM` | Error-exit on blank or unrecognised value; validated against `valid_complaint_types` config |
| `location` | Glass only | `WS`, `back`, `side` | Required for Glass — error if blank |
| `action` | Glass/WS only | `Replace`, `Repair` | Required when `Type=Glass` and `location=WS`; ignored for back/side |

Comment lines (`#`) skipped by both scripts.

---

## Code Changes

### `playwright_prototype/steps.py`

1. **Add `COMPLAINT_TYPE_PATTERNS`** (moved from `close_workitem.py`):
   ```python
   COMPLAINT_TYPE_PATTERNS = {
       "Glass": re.compile(r"glass|windshield|crack|chip|window", re.I),
       "PM":    re.compile(r"PM", re.I),
   }
   ```

2. **Rename `check_existing_glass_work_item` → `check_existing_work_item(page, mva, type)`**
   Uses `COMPLAINT_TYPE_PATTERNS[type]` to match the correct open tile.

3. **Update `handle_complaint_dialog(page, mva, type, location, action)`**
   After drivability, branch by type:
   - `Glass`: existing path — clicks "Glass Damage" → damage subtype → Submit
   - `PM`: clicks "PM" → Additional Info screen (leave checkbox unchecked, skip photo) → Submit Complaint

4. **Rename `select_glass_opcode` → `select_opcode(page, type)`**
   - `Glass`: selects "Glass Repair/Replace" (unchanged)
   - `PM`: reads `pm_opcode` from config; selects it if set; skips the step if unset.
     If the app requires an opcode, Create Work Item button will be disabled → timeout → clear error.

### `WorkItems/create_workitem.py`

- Log file path: `WorkItems/create_workitem.log`
- Default CSV path: `WorkItems/create_workitem.csv`
- `load_csv`: add `type` field with validation per rules above; default `Type="Glass"` for backward compatibility
- `process_mva(page, mva, type, location, action)`: thread `type` through all step calls
- Update imports: `check_existing_work_item`, `select_opcode`

### `WorkItems/close_workitem.py`

- Log file path: `WorkItems/close_workitem.log`
- Default CSV path: `WorkItems/close_workitem.csv`
- Import `COMPLAINT_TYPE_PATTERNS` from `playwright_prototype.steps` (remove local definition)
- `_load_csv`: add comment-line skipping

---

## Config Additions

| Key | Type | Default | Purpose |
|---|---|---|---|
| `pm_opcode` | string or null | `null` | Opcode name for PM work items. If null, opcode step is skipped. |

---

## PM Create Flow

Steps in order — unknowns resolved via first `--pause` trial run:

1. `navigate_to_mva`
2. `check_existing_work_item` — PM pattern
3. `click_add_work_item`
4. `handle_complaint_dialog` — Drivability (config) → **PM** button → Additional Info screen (skip checkbox, skip photo) → Submit Complaint
5. `complete_mileage_dialog`
6. `select_opcode` — skip if `pm_opcode` unset; select if set
7. `create_work_item`
8. `confirm_completion`

All PM-specific steps log at INFO with `[STEPS] PM:` prefix for easy trace reading.

### Known unknowns — resolve via `--pause` trial

| Question | Signal |
|---|---|
| Does PM require an opcode? | Create Work Item button disabled after mileage → add opcode name to `pm_opcode` config |
| Does Additional Info checkbox need explicit unchecking? | Observe default state on first `--pause` run |

---

## Out of Scope

- Tire Damage, Body Damage, and other complaint types — deferred until PM trial complete
- Renaming `open_glass_work_item_tile` / `complete_glass_work_item` — work generically for close flow via pattern matching; rename deferred
- Changes to `verify_workitem.py` internals — move only, no functional changes in this pass
