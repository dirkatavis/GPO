# Work Item Type Routing — Design Spec
_Date: 2026-05-22_

## Goal

Generalize the create and close work item scripts to support multiple work item types via a shared CSV schema, and consolidate all related files into a single `WorkItems/` folder. Initial types: **Glass** (existing, proven) and **PM** (new, to be trialled via `--pause`).

---

## Unified CSV Schema

Both scripts accept the same file format:

```
mva,Type,location,action
61444283,Glass,WS,Replace
57503994,Glass,back,
61119446,PM,,
```

### Column rules

| Column | Required? | Values | Notes |
|---|---|---|---|
| `mva` | Always | number | Blank rows skipped |
| `Type` | Always | `Glass`, `PM` | Error-exit on blank or unrecognised value |
| `location` | Glass only | `WS`, `back`, `side` | Required for Glass — error if blank |
| `action` | Glass/WS only | `Replace`, `Repair` | Required when `Type=Glass` and `location=WS`; ignored for back/side |

- Comment lines starting with `#` are skipped by both scripts.
- `Type` is validated against `valid_complaint_types` in config (default `["Glass", "PM"]`).

---

## Folder Structure

Everything moves into a self-contained `WorkItems/` folder. Files follow a consistent `<script_name>.*` naming pattern.

```
WorkItems/
  create_workitem.py        ← was playwright_prototype/main.py
  close_workitem.py         ← was close_workitem.py (root)
  create_workitem.csv       ← was sample_mvas.csv (input for create)
  close_workitem.csv        ← new (input for close)
  create_workitem.log       ← was playwright_prototype.log
  close_workitem.log        ← existing close log, moved here
  playwright_prototype/     ← support package, moves in from root
    __init__.py
    steps.py
    session.py
    config.py
    login.py
    profile_launch_check.py
```

`COMPLAINT_TYPE_PATTERNS` moves from `close_workitem.py` into `playwright_prototype/steps.py` so both scripts share one definition.

---

## Changes by File

### `playwright_prototype/steps.py`

1. **Add `COMPLAINT_TYPE_PATTERNS`** (moved from `close_workitem.py`):
   ```python
   COMPLAINT_TYPE_PATTERNS = {
       "Glass": re.compile(r"glass|windshield|crack|chip|window", re.I),
       "PM":    re.compile(r"PM", re.I),
   }
   ```

2. **Rename `check_existing_glass_work_item` → `check_existing_work_item(page, mva, type)`**
   Uses `COMPLAINT_TYPE_PATTERNS[type]` to find the right open tile.

3. **Update `handle_complaint_dialog(page, mva, type, location, action)`**
   After drivability, branch by type:
   - `Glass`: existing path — clicks "Glass Damage" → damage subtype → Submit
   - `PM`: clicks "PM" → Additional Info screen (leave checkbox unchecked, skip photo) → Submit Complaint

4. **Rename `select_glass_opcode` → `select_opcode(page, type)`**
   - `Glass`: selects "Glass Repair/Replace" (unchanged)
   - `PM`: reads `pm_opcode` from config; selects it if set; skips the step entirely if unset.
     If the app requires an opcode, Create Work Item will be disabled → timeout → clear error telling us to add the opcode name to config.

### `WorkItems/create_workitem.py` (was `playwright_prototype/main.py`)

- Moved to `WorkItems/` and renamed.
- Log file path updated to `WorkItems/create_workitem.log`.
- Default CSV path updated to `WorkItems/create_workitem.csv`.
- `load_csv`: add `type` field; validate Glass requires `location`; validate WS requires `action`; default `Type="Glass"` for backward compatibility with bare MVA lists.
- `process_mva(page, mva, type, location, action)`: thread `type` through all step calls.
- Update imports: `check_existing_work_item`, `select_opcode`.

### `WorkItems/close_workitem.py` (was `close_workitem.py` at root)

- Moved to `WorkItems/` folder.
- Log file path updated to `WorkItems/close_workitem.log`.
- Default CSV path updated to `WorkItems/close_workitem.csv`.
- Import `COMPLAINT_TYPE_PATTERNS` from `playwright_prototype.steps` (remove local definition).
- `_load_csv`: add comment-line skipping.

### `WorkItems/create_workitem.csv` (was `playwright_prototype/sample_mvas.csv`)

- Renamed and moved to `WorkItems/`.
- Updated comment header documenting unified schema.
- Header row: `mva,Type,location,action`.
- Existing Glass MVAs: add `Glass` in Type column; fill `location`/`action`.

### `WorkItems/close_workitem.csv` (new)

- Same schema as `create_workitem.csv`.
- Seeded with same comment header; data rows left for user to populate.

---

## Config Additions

| Key | Type | Default | Purpose |
|---|---|---|---|
| `pm_opcode` | string or null | `null` | Opcode name for PM work items. If null, opcode step is skipped. |

---

## PM Create Flow (known steps)

1. `navigate_to_mva`
2. `check_existing_work_item` — PM pattern
3. `click_add_work_item`
4. `handle_complaint_dialog` — Drivability (config) → **PM** button → Additional Info screen (skip checkbox + photo) → Submit Complaint
5. `complete_mileage_dialog`
6. `select_opcode` — skip if `pm_opcode` unset; select if set
7. `create_work_item`
8. `confirm_completion`

---

## Known Unknowns — Resolve via `--pause` Trial

| Question | Discovery method |
|---|---|
| Does PM require an opcode? | If Create Work Item is disabled after mileage, opcode is required — add name to `pm_opcode` config |
| Does Additional Info checkbox need explicit unchecking? | Observe state on first `--pause` run |

All PM-specific steps log at INFO with `[STEPS] PM:` prefix for easy trace reading.

---

## Out of Scope

- Tire Damage, Body Damage, and other complaint types — deferred until PM trial complete.
- Renaming `open_glass_work_item_tile` / `complete_glass_work_item` — functions already work generically for close flow via pattern matching; rename deferred.
- Any callers outside `WorkItems/` that currently reference `playwright_prototype` or `close_workitem` at the root — audit and update import paths as part of the move.
