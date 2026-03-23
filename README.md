# GlassOrchestrator (GPO)

A modular Python pipeline for vehicle glass procurement, built on a **6-phase architecture**.

## Architecture

| Phase | Name | Description |
|-------|------|-------------|
| 1 | **Input** | Fetch scan data from Gmail (`export@orcascan.com`) via IMAP |
| 2 | **Parsing** | Regex triage (`^(\d{8})([rc]*)$`), build session manifest |
| 3 | **Worker** | Write MVAs to CSV, invoke `GlassDataParser.py` subprocess |
| 4 | **Data Merge** | Left-join manifest with scraper results; missing VIN → `N/A` |
| 5 | **Persistence** | Append to Google Sheet (`GlassClaims` tab), idempotent on `MVA+Arrival Date` |
| 6 | **Notification** | HTML email for Replacement items; red-flagged rows for missing VINs |

## Suffix Rules

| Suffix | Field | Value | Default (no suffix) |
|--------|-------|-------|---------------------|
| `r` | Damage Type | Repair | Replacement |
| `c` | Claim# | Listed | Missing |

## Data Contract — `ATL_Data 2026 : GlassClaims`

The pipeline output maps 1-to-1 with the `GlassClaims` tab in the master workbook.
Phase 5 inserts rows above the summary section; the idempotency key is **`MVA | Arrival Date`**.

| # | Column | Source | Phase | Notes |
|---|--------|--------|-------|-------|
| 1 | **Arrival Date** | Email `Date` header | 2 | `MM/DD/YYYY` |
| 2 | **MVA** | Orca Scan Description | 2 | 8-digit, suffixes stripped |
| 3 | **VIN** | CGI scraper (`GlassResults.txt`) | 4 | `N/A` if scraper miss |
| 4 | **Make** | CGI scraper `Desc` column | 4 | Populated by Phase 4 merge |
| 5 | **Location** | Constant `APO` | 2 | Always `APO` |
| 6 | **Damage Type** | Suffix `r` → Repair | 2 | Default: `Replacement` |
| 7 | **Claim#** | Suffix `c` → Listed | 2 | Default: `Missing` |
| 8 | **WorkItem** | Pipeline flag | 2 | Always `verified` |

## Setup

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `GLASS_EMAIL_ACCOUNT` | Gmail address for IMAP login |
| `GLASS_EMAIL_PASSWORD` | Gmail app password |
| `GLASS_SENDER` | From address for outbound notifications |
| `GLASS_NOTIFY_RECIPIENTS` | Comma-separated recipient list |

Phase 5 also requires a **Google Service Account** JSON key file at `Service_account.json` in the project root,
with Editor access to the target spreadsheet.

## Usage

```bash
Run-GlassOrchestrator.cmd
```

`Run-GlassOrchestrator.cmd` bootstraps the runtime by creating `.venv` (if missing),
installing `requirements.txt`, then launching `GlassOrchestrator.py` with the venv interpreter.

Or run directly with the virtual environment interpreter:

```bash
.venv\Scripts\python.exe GlassOrchestrator.py
```

## File Layout

```
GlassOrchestrator.py     # Main 6-phase pipeline
Service_account.json     # Google service account key (not committed)
src/
  GlassDataParser.py    # Phase 3 worker (Selenium scraper)
core/
flows/
pages/
utils/
config/
data/
  GlassDataParser.csv    # Phase 3 input (auto-generated)
GlassResults.txt         # Phase 3 output (worker-produced)
```

## Failure Handling

- Each phase is wrapped in its own `try/except` block.
- **Phase 3 failure aborts the entire pipeline** — no data is persisted or notified.
- Phase 6 (notification) failure is logged but does not lose persisted data.
