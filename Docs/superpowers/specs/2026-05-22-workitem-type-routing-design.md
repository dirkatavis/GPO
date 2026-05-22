# Work Item Type Routing — Design Spec
_Date: 2026-05-22_

## Goal

Generalize the create (`playwright_prototype/main.py`) and close (`close_workitem.py`) scripts to support multiple work item types via a shared CSV schema. Initial types: **Glass** (existing, proven) and **PM** (new, to be trialled via `--pause`).

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

## Architecture

```
steps.py                         ← shared step functions + COMPLAINT_TYPE_PATTERNS
playwright_prototype/main.py     ← create flow (CSV → per-MVA work item creation)
close_workitem.py                ← close flow (CSV → per-MVA work item close)
sample_mvas.csv                  ← shared input file
```

`COMPLAINT_TYPE_PATTERNS` moves from `close_workitem.py` into `steps.py` so both scripts use one definition.

---

## Changes by File

### `steps.py`

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

### `playwright_prototype/main.py`

- `load_csv`: add `type` field; validate Glass requires `location`; validate WS requires `action`; default `Type="Glass"` for backward compatibility with bare MVA lists.
- `process_mva(page, mva, type, location, action)`: thread `type` through all step calls.
- Update imports: `check_existing_work_item`, `select_opcode`.

### `close_workitem.py`

- Import `COMPLAINT_TYPE_PATTERNS` from `steps.py` (remove local definition).
- `_load_csv`: add comment-line skipping (same pattern as `main.py`).

### `sample_mvas.csv`

- Updated comment header documenting unified schema.
- Header row: `mva,Type,location,action`.
- Existing Glass MVAs: add `Glass` in Type column; fill `location`/`action`.

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
