# GlassOrchestrator (GPO)

A modular Python pipeline for vehicle glass procurement, built on a **6-phase architecture**.

## Architecture

| Phase | Name | Description |
|-------|------|-------------|
| 1 | **Input** | Fetch scan data from Gmail (`export@orcascan.com`) via IMAP |
| 2 | **Parsing** | Regex triage (`^(\d{8})([rc]*)$`), build session manifest |
| 3 | **Worker** | Write MVAs to CSV, invoke `GlassDataParser.py` subprocess |
| 4 | **Data Merge** | Left-join manifest with scraper results; missing VIN → `N/A` |
| 5 | **Persistence** | Append to `MasterLog.xlsx` (`GlassClaims` tab), idempotent on MVA+Date |
| 6 | **Notification** | HTML email for Replacement items; red-flagged rows for missing VINs |

## Suffix Rules

| Suffix | Field | Value | Default (no suffix) |
|--------|-------|-------|---------------------|
| `r` | WorkType | Repair | Replacement |
| `c` | ClaimStatus | Claim Generated | Pending |

## Output Columns

`Date`, `MVA`, `VIN`, `Description`, `Location` (APO), `WorkType`, `ClaimStatus`

## Setup

```bash
pip install -r requirements.txt
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `GLASS_EMAIL_ACCOUNT` | Gmail address for IMAP login |
| `GLASS_EMAIL_PASSWORD` | Gmail app password |
| `GLASS_SENDER` | From address for outbound notifications |
| `GLASS_NOTIFY_RECIPIENTS` | Comma-separated recipient list |

## Usage

```bash
python GlassOrchestrator.py
```

## File Layout

```
GlassOrchestrator.py     # Main 6-phase pipeline
GlassDataParser.py       # External worker (scraper)
data/
  GlassDataParser.csv    # Phase 3 input (auto-generated)
GlassResults.txt         # Phase 3 output (worker-produced)
MasterLog.xlsx           # Phase 5 system of record
```

## Failure Handling

- Each phase is wrapped in its own `try/except` block.
- **Phase 3 failure aborts the entire pipeline** — no data is persisted or notified.
- Phase 6 (notification) failure is logged but does not lose persisted data.
