# Glass Damage Work Item Automation Requirements

## Overview
This document defines the requirements for a Python automation script that processes a list of MVAs (Motor Vehicle Assets) to ensure that a glass damage work item exists for each. The script will interact with the Compass web application using Selenium, leveraging existing flows and logging utilities.

## Functional Requirements

### 1. MVA Processing
- The script shall read a list of MVAs from a CSV file (default: `data/mva.csv`).
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
End of requirements.
