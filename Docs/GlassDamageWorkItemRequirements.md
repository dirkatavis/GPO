# Glass Damage Work Item Automation Requirements

## Overview
This document defines the requirements for a Python automation script that processes a list of MVAs (Motor Vehicle Assets) to ensure that a glass damage work item exists for each. The script will interact with the Compass web application using Selenium, leveraging existing flows and logging utilities.

## Functional Requirements

> **Note:** The CSV-based input below describes the original standalone script design.
> Phase 7 (see below) supersedes this with Google Sheet input. The CSV flow is legacy/out-of-scope
> for the current implementation.

### 1. MVA Processing
- The script shall read a list of MVAs from a CSV file (default: `data/mva.csv`). *(legacy — see Phase 7)*
- For each MVA, the script shall:
  - Log the start of the review for the MVA.

### 2. Work Item Detection and Creation
- The script shall check if an active (open) glass damage work item exists for the MVA.
  - If an active glass damage work item exists:
    - Log that an existing work item was found.
    - Do not create a new work item.
  - If no active glass damage work item exists:
    - Attempt to create a new glass damage work item for the MVA.
    - The script shall not require a pre-existing glass damage complaint to create a work item.
    - If the work item creation flow requires a complaint, the script shall handle creating or associating a complaint as needed.
    - Log the result of the work item creation (success or failure).

### 3. Error Handling
- The script shall log any errors encountered during processing, including exceptions and failed work item creation attempts.

## Logging Requirements (Two-Tier Logging)
- The script shall use the existing centralized logger (`utils/logger.py`).
- The logger must be configured to write all log output to a file named `results.log` located in a `log` subdirectory of the project root (i.e., `./log/results.log`).
- The log shall include:
  1. The MVA being reviewed.
  2. Whether a glass damage work item was found or created.
  3. Any errors or exceptions encountered.
- Log messages shall be clear and indicate the action taken for each MVA.

## Integration & Dependencies
- The script shall use existing flows and page objects for work item and complaint handling (e.g., `flows/work_item_flow.py`, `flows/complaints_flows.py`).
- The script shall use the Selenium WebDriver for web automation.
- The script shall use the existing logger for all logging.

## Input/Output
- **Input:** `data/mva.csv` (list of MVAs, one per line)
- **Output:** Logging to the configured log output (console or file, as set in logger config)

## Non-Functional Requirements
- The script shall be robust to missing or malformed MVA entries in the input CSV.
- The script shall continue processing remaining MVAs if an error occurs with one.
- The script shall be maintainable and follow the code patterns established in the project.

## Example Workflow
1. Read MVA from CSV.
2. Log: "[MVA] Reviewing {mva}"
3. If glass damage work item exists:
   - Log: "[GLASS] Glass damage work item already exists for {mva}"
4. Else:
   - Log: "[GLASS] No active glass damage work item found for {mva}, creating new work item..."
   - Attempt to create work item.
   - Log success or error.
5. On error:
   - Log: "[ERROR] Exception for {mva}: {error}"

## Out of Scope
- Manual review or intervention for failed MVAs.
- UI or reporting beyond logging.

---

## Phase 7 — Standalone Work Item Creation Script

### What it does
Phase 7 runs as a separate manual step after the main Phase 1–6 pipeline completes. It reads eligible MVAs directly from the `GlassClaims` Google Sheet and creates Compass glass damage work items for any that do not already have one.

### Entry point
`GlassWorkItems.py` (root) — run via `Run-GlassWorkItems.cmd` or directly with `.venv\Scripts\python.exe GlassWorkItems.py`

### Operator workflow
1. Run Phase 1–6 pipeline (`Run-GlassOrchestrator.cmd`)
2. Optionally fill in the `Location` column on `GlassClaims` sheet (`Windshield` / `Side` / `Rear`; blank defaults to `Windshield`)
3. Run `Run-GlassWorkItems.cmd`

### Manifest contract
Phase 7 reads from the `GlassClaims` sheet and builds a manifest of plain dicts:

| Key | Source | Default |
|---|---|---|
| `mva` | `MVA` column | required |
| `damage_type` | `Damage Type` column | `"Replacement"` |
| `location` | `Location` column | `"WINDSHIELD"` |

Only rows where `is_notification_eligible(row) == True` (Replacement) and `WorkItemCreated` is blank are included.

### Return contract
`run_glass_work_item_phase()` returns:
```python
{"processed": n, "created": n, "skipped": n, "failed": n}
```

### Skip behavior
If `check_existing_work_item()` finds an open glass work item for the MVA, the row is skipped and counted as `skipped`. No duplicate is created.

### Failure behavior
Any exception on a single MVA increments `failed` and processing continues. The loop never aborts. All MVAs are always attempted.

### Idempotency
On successful creation, `WorkItemCreated = Y` is written back to the sheet. Subsequent runs skip that row because `WorkItemCreated` is no longer blank.

### Known limitation
Glass location (Windshield / Side / Rear) is not present in the Orca Scan email data. The `Location` column must be filled in manually by the operator if non-windshield damage is involved. When blank, all items default to `Windshield` — correct for the vast majority of current cases.

---

## WorkItemHandler Extension Guide

Use this guide when adding a new work item type (e.g. PM, Brake).

### The pattern
`WorkItemHandler` (in `flows/work_item_handler.py`) is an ABC. Subclass it, implement four methods, register in the factory. Nothing else changes.

### Step 1 — Subclass `WorkItemHandler`

```python
class PMWorkItemHandler(WorkItemHandler):
    ...
```

### Step 2 — Implement the four abstract methods

| Method | Responsibility |
|---|---|
| `detect_complaints(self, driver) -> list` | Return complaint tile elements relevant to this work item type. Use a type-specific detection function from `complaints_flows.py`. |
| `should_handle_existing_complaint(self, complaint_text: str) -> bool` | Return `True` if the tile text matches this work item type. Used by the base class to filter tiles returned by `detect_complaints()`. |
| `create_new_complaint(self, config: WorkItemConfig) -> dict` | UI flow to create a new complaint when none exists. Return `{"status": "created"}` on success. |
| `handle_existing_complaint(self, config: WorkItemConfig, complaint_element) -> dict` | UI flow to associate an existing complaint. Return `{"status": "created"}` on success. |

### Step 3 — Add a detection function to `complaints_flows.py`

```python
def detect_pm_complaints(driver, mva: str) -> list:
    """Detect complaint tiles containing PM keywords."""
    # Always use the dynamic-suffix-safe selector:
    tiles = driver.find_elements(
        By.XPATH, "//div[contains(@class,'fleet-operations-pwa__complaintItem__')]"
    )
    keywords = ["pm", "preventive maintenance"]
    return [t for t in tiles if any(k in t.text.lower() for k in keywords)]
```

### Step 4 — Register in the factory

```python
def create_work_item_handler(work_item_type: str, driver) -> WorkItemHandler:
    if work_item_type.upper() == "GLASS":
        return GlassWorkItemHandler(driver)
    if work_item_type.upper() == "PM":          # ← add this
        return PMWorkItemHandler(driver)
    raise ValueError(f"Unsupported work item type: {work_item_type}")
```

### Selector rule (non-negotiable)
Compass generates class names with runtime hash suffixes. Always use partial-class matching:
- XPath: `contains(@class, "fleet-operations-pwa__complaintItem")`
- CSS: `[class*="fleet-operations-pwa__complaintItem"]`

Never use full hardcoded class names — they break on every Compass rebuild.

---
End of requirements.
