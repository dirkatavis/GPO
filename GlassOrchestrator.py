"""Vehicle glass procurement pipeline orchestrator.

Pipeline steps:
    1. Fetch scan data from Gmail (export@orcascan.com)
    2. Parse and normalize MVA entries
    3. Invoke scraper worker subprocess
    4. Merge scraper output with session manifest
    5. Persist new rows to Google Sheet
    6. Send replacement notifications
"""

import csv
import email
import imaplib
import json
import logging
import os
import re
import smtplib
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import getaddresses
from pathlib import Path
from typing import Any

try:
    import gspread  # pylint: disable=import-error  # pyright: ignore[reportMissingImports]
except ModuleNotFoundError:
    gspread = None  # type: ignore[assignment]
import pandas as pd
from cycle_tracker import CycleTracker

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

# ─── Configuration ────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CSV_PATH = DATA_DIR / "GlassDataParser.csv"
RESULTS_PATH = BASE_DIR / "GlassResults.txt"
WORKER_SCRIPT = BASE_DIR / "src" / "GlassDataParser.py"

ORCHESTRATOR_CONFIG_PATH = BASE_DIR / "orchestrator_config.json"
ORCHESTRATOR_PROJECT_CONFIG_PATH = BASE_DIR / "orchestrator_project.json"
ORCHESTRATOR_PROJECT_LOCAL_CONFIG_PATH = BASE_DIR / "orchestrator_project.local.json"
ORCHESTRATOR_LOCAL_CONFIG_PATH = BASE_DIR / "orchestrator_config.local.json"
SHARED_LOCAL_CONFIG_PATH = BASE_DIR / "config" / "config.local.json"


def _load_runtime_config(config_path: Path) -> dict:
    """Load runtime configuration from JSON with sane defaults."""
    defaults = {
        "sheet_name": "GlassClaims",
        "imap_server": "imap.gmail.com",
        "smtp_server": "smtp.gmail.com",
        "smtp_port": 587,
        "target_sender": "export@orcascan.com",
        "mva_pattern": r"^(\d{8})([A-Z]+)([r]?)([c]?)$",
        "areas": {
            "WS":  "Windshield",
            "FLD": "Front Left Door",
            "FRD": "Front Right Door",
            "RLD": "Rear Left Door",
            "RRD": "Rear Right Door",
            "FLV": "Front Left Vent",
            "FRV": "Front Right Vent",
            "BW":  "Back Window",
            "SR":  "Sunroof",
            "RLQ": "Rear Left Quarter",
            "RRQ": "Rear Right Quarter",
        },
        "repair_eligible_areas": ["WS"],
        "vendor_labels": {
            "Repair":      "Repair(SuperGlass)",
            "Replacement": "Replace(AGN)",
        },
        "cycle_tracker_store": "data/mva_cycle_tracker.json",
        "cycle_gap_grace_days": 1,
        "cycle_completed_retention": 1000,
        "location": "APO",
        "columns": [
            "Arrival Date",
            "MVA",
            "FPO#",
            "VIN",
            "Make",
            "Location",
            "Action",
            "Area",
            "Claim#",
            "WorkItem",
        ],
        "notify_recipients": [],
    }

    if not config_path.exists():
        return defaults

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if not isinstance(loaded, dict):
            return defaults
        merged = defaults.copy()
        merged.update(loaded)
        return merged
    except (OSError, json.JSONDecodeError) as exc:
        logging.getLogger("GlassOrchestrator").warning(
            "Config load failed for %s; using defaults (%s)", config_path, exc
        )
        return defaults


def _load_local_config_overrides(config_path: Path) -> dict:
    """Load optional local JSON overrides for machine-specific configuration."""
    if not config_path.exists():
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if not isinstance(loaded, dict):
            return {}
        return loaded
    except (OSError, json.JSONDecodeError) as exc:
        logging.getLogger("GlassOrchestrator").warning(
            "Local config override load failed for %s; ignoring (%s)", config_path, exc
        )
        return {}


def _resolve_config_path(path_value: str) -> Path:
    """Resolve relative config paths from BASE_DIR and keep absolute paths intact."""
    path = Path(path_value)
    if path.is_absolute():
        return path
    return BASE_DIR / path


def _compile_regex_with_fallback(pattern_text: str, fallback_text: str) -> re.Pattern[str]:
    """Compile regex from config; fall back to a known-safe pattern on error."""
    try:
        return re.compile(pattern_text)
    except re.error as exc:
        logging.getLogger("GlassOrchestrator").warning(
            "Invalid regex in config (%s). Using fallback pattern.", exc
        )
        return re.compile(fallback_text)


RUNTIME_CONFIG = _load_runtime_config(ORCHESTRATOR_CONFIG_PATH)
RUNTIME_CONFIG.update(_load_runtime_config(ORCHESTRATOR_PROJECT_CONFIG_PATH))
RUNTIME_CONFIG.update(_load_local_config_overrides(ORCHESTRATOR_PROJECT_LOCAL_CONFIG_PATH))

# Legacy local overrides kept for backward compatibility.
RUNTIME_CONFIG.update(_load_local_config_overrides(ORCHESTRATOR_LOCAL_CONFIG_PATH))

# Shared local overrides can still be used for cross-module machine settings.
RUNTIME_CONFIG.update(_load_local_config_overrides(SHARED_LOCAL_CONFIG_PATH))

# Google Sheets target
SERVICE_ACCOUNT_JSON = _resolve_config_path(str(RUNTIME_CONFIG["service_account_json"]))
SPREADSHEET_ID = os.getenv("GLASS_SPREADSHEET_ID", str(RUNTIME_CONFIG["spreadsheet_id"]))
SHEET_NAME = str(RUNTIME_CONFIG["sheet_name"])

# Gmail/SMTP infrastructure endpoints
IMAP_SERVER = str(RUNTIME_CONFIG["imap_server"])
SMTP_SERVER = str(RUNTIME_CONFIG["smtp_server"])
SMTP_PORT = int(RUNTIME_CONFIG["smtp_port"])

# Gmail credentials — env vars take priority; fall back to orchestrator_config values
EMAIL_ACCOUNT = os.getenv("GLASS_EMAIL_ACCOUNT") or str(RUNTIME_CONFIG.get("email_account", ""))
EMAIL_PASSWORD = os.getenv("GLASS_EMAIL_PASSWORD") or str(RUNTIME_CONFIG.get("email_password", ""))
SENDER_ADDRESS = os.getenv("GLASS_SENDER") or str(RUNTIME_CONFIG.get("sender_address", ""))

# Runtime business/config values
notify_recipients_env = os.getenv("GLASS_NOTIFY_RECIPIENTS", "").strip()
if notify_recipients_env:
    NOTIFY_RECIPIENTS = [x.strip() for x in notify_recipients_env.split(",") if x.strip()]
else:
    NOTIFY_RECIPIENTS = [
        x.strip() for x in RUNTIME_CONFIG.get("notify_recipients", []) if isinstance(x, str) and x.strip()
    ]

TARGET_SENDER = str(RUNTIME_CONFIG["target_sender"])
MVA_PATTERN = _compile_regex_with_fallback(
    str(RUNTIME_CONFIG.get("mva_pattern", r"^(\d{8})([A-Z]+)([r]?)([c]?)$")),
    r"^(\d{8})([A-Z]+)([r]?)([c]?)$",
)
AREAS: dict[str, str] = dict(RUNTIME_CONFIG.get("areas", {}))
REPAIR_ELIGIBLE_AREAS: set[str] = set(RUNTIME_CONFIG.get("repair_eligible_areas", ["WS"]))
VENDOR_LABELS: dict[str, str] = dict(RUNTIME_CONFIG.get("vendor_labels", {
    "Repair": "Repair(SuperGlass)",
    "Replacement": "Replace(AGN)",
}))
LOCATION = str(RUNTIME_CONFIG["location"])
COLUMNS = list(RUNTIME_CONFIG["columns"])
CYCLE_TRACKER_STORE = _resolve_config_path(str(RUNTIME_CONFIG.get("cycle_tracker_store", "data/mva_cycle_tracker.json")))
CYCLE_GAP_GRACE_DAYS = int(RUNTIME_CONFIG.get("cycle_gap_grace_days", 1))
CYCLE_COMPLETED_RETENTION = int(RUNTIME_CONFIG.get("cycle_completed_retention", 1000))


# The phase terminalogy should be seen as a design process but not an archetetual method
# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(BASE_DIR / "GlassOrchestrator.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("GlassOrchestrator")


@dataclass(frozen=True)
class InboundEmail:
    """Normalized inbound email data extracted from a MIME message."""
    from_address: str
    to_addresses: list[str]
    subject: str
    sent_at: datetime
    body_text: str
    body_html: str

    @property
    def best_body(self) -> str:
        """Prefer HTML body when it contains tabular data, otherwise use plain text."""
        if self.body_html and "<table" in self.body_html.lower():
            return self.body_html
        return self.body_text or self.body_html

    @classmethod
    def from_message(cls, msg: email.message.Message) -> "InboundEmail":
        """Build a parsed email object from a MIME message."""
        body_text, body_html = _extract_message_bodies(msg)
        from_addresses = _extract_header_addresses(msg.get_all("From", []))
        to_addresses = _extract_header_addresses(msg.get_all("To", []))
        return cls(
            from_address=from_addresses[0] if from_addresses else "",
            to_addresses=to_addresses,
            subject=msg.get("Subject", ""),
            sent_at=_parse_email_datetime(msg.get("Date", "")),
            body_text=body_text,
            body_html=body_html,
        )


@dataclass(frozen=True)
class OutboundEmail:
    """Normalized outbound email payload used for SMTP delivery."""
    subject: str
    html_body: str
    sender: str
    recipients: list[str]

# ─── Input Acquisition ────────────────────────────────────────────────────────

def fetch_input_descriptions() -> tuple[list[tuple[str, str]], datetime]:
    """
    Connect to Gmail via IMAP, fetch the latest UNSEEN email from the
    target sender, and extract:
      - A list of (type_value, description) tuples from the email table
      - The Date header parsed as a datetime object
    """
    log.info("Input acquisition: Connecting to Gmail IMAP …")

    mail = _connect_to_inbox()
    try:
        unseen_ids = _find_unseen_message_ids(mail)
        if not unseen_ids:
            log.warning("Input: No unseen messages from %s", TARGET_SENDER)
            return [], datetime.now()

        log.info("Input: Found %d unseen message(s)", len(unseen_ids))
        latest_message = _fetch_message_by_id(mail, unseen_ids[-1])
        return _extract_descriptions_from_message(latest_message)

    finally:
        try:
            mail.logout()
        except (imaplib.IMAP4.error, OSError):
            pass


def _connect_to_inbox() -> imaplib.IMAP4_SSL:
    """Open IMAP connection, authenticate, and select inbox."""
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
    mail.select("inbox")
    return mail


def _find_unseen_message_ids(mail: imaplib.IMAP4_SSL) -> list[bytes]:
    """Return unseen message IDs for the configured target sender."""
    search_criteria = f'(UNSEEN FROM "{TARGET_SENDER}")'
    status, msg_ids = mail.search(None, search_criteria)
    if status != "OK" or not msg_ids or not msg_ids[0]:
        return []
    return msg_ids[0].split()


def _fetch_message_by_id(mail: imaplib.IMAP4_SSL, message_id: bytes) -> email.message.Message:
    """Fetch and decode a single RFC822 message by IMAP id."""
    status, msg_data = mail.fetch(message_id, "(RFC822)")
    if status != "OK" or not msg_data or not msg_data[0]:
        raise RuntimeError(f"Failed to fetch message id {message_id}")

    raw_email = msg_data[0][1]
    if not raw_email:
        raise RuntimeError(f"Empty message payload for id {message_id}")
    return email.message_from_bytes(raw_email)


def _extract_descriptions_from_message(msg: email.message.Message) -> tuple[list[tuple[str, str]], datetime]:
    """Extract parsed (type_value, description) tuples and parsed email datetime from a MIME message."""
    return _extract_descriptions_from_email(InboundEmail.from_message(msg))


def _extract_descriptions_from_email(parsed_email: InboundEmail) -> tuple[list[tuple[str, str]], datetime]:
    """Extract parsed (type_value, description) tuples and email datetime from normalized email data."""
    log.info("Input: Email date = %s", parsed_email.sent_at.isoformat())

    body = parsed_email.best_body
    if "<table" in body.lower():
        descriptions = _parse_html_descriptions(body)
    else:
        descriptions = _parse_descriptions(body)
    log.info("Input: Extracted %d description lines", len(descriptions))
    return descriptions, parsed_email.sent_at


def _parse_email_datetime(date_str: str) -> datetime:
    """Parse email Date header into datetime, falling back to current time."""
    if not date_str:
        return datetime.now()
    try:
        return email.utils.parsedate_to_datetime(date_str)
    except (TypeError, ValueError):
        return datetime.now()


def _extract_header_addresses(header_values: list[str]) -> list[str]:
    """Extract email addresses from RFC822 header values."""
    return [addr for _, addr in getaddresses(header_values) if addr]


def _extract_message_bodies(msg: email.message.Message) -> tuple[str, str]:
    """Extract plain and html bodies from a MIME message."""
    plain = ""
    html = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            decoded = payload.decode("utf-8", errors="replace")
            if content_type == "text/plain" and not plain:
                plain = decoded
            elif content_type == "text/html" and not html:
                html = decoded
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            decoded = payload.decode("utf-8", errors="replace")
            if content_type == "text/html":
                html = decoded
            else:
                plain = decoded
    return plain, html

def _extract_body(msg: email.message.Message) -> str:
    """Walk a MIME message and return the best body for parsing.

    Orca Scan emails contain an HTML table with structured data and a
    plain-text CSV attachment.  We prefer the HTML when it contains a
    <table> because the CSV embeds newlines inside quoted fields which
    break simple line-by-line parsing.
    """
    body_text, body_html = _extract_message_bodies(msg)
    if body_html and "<table" in body_html.lower():
        return body_html
    return body_text or body_html


def _parse_descriptions(body: str) -> list[tuple[str, str]]:
    """
    Parse the email body as CSV or line-delimited text and return
    (type_value, description) tuples.

    For CSV with Type and Description columns, extracts both.
    For plain text fallback, returns empty type_value.
    """
    lines = body.strip().splitlines()
    if not lines:
        return []

    # Try CSV with a 'Description' header first
    reader = csv.DictReader(lines)
    if reader.fieldnames and "Description" in reader.fieldnames:
        has_type = "Type" in reader.fieldnames
        results: list[tuple[str, str]] = []
        for row in reader:
            desc = row.get("Description", "").strip()
            if desc:
                type_val = row.get("Type", "").strip() if has_type else ""
                results.append((type_val, desc))
        return results

    # Fallback: treat each non-empty line as a description (no type_value)
    return [("", line.strip()) for line in lines if line.strip()]


def _parse_html_descriptions(html: str) -> list[tuple[str, str]]:
    """
    Extract 'Type' and 'Description' column values from an HTML table (Orca Scan email).
    Uses BeautifulSoup if available, otherwise falls back to regex.

    Returns:
        List of (type_value, description) tuples. Each Description cell may contain
        multiple MVA codes (newline-separated), so one row can produce multiple tuples
        sharing the same type_value.
    """
    if HAS_BS4:
        return _parse_html_descriptions_bs4(html)

    return _parse_html_descriptions_regex(html)


def _parse_html_descriptions_bs4(html: str) -> list[tuple[str, str]]:
    """Parse Type and Description values from Orca Scan HTML using BeautifulSoup."""
    soup = BeautifulSoup(html, "html.parser")
    table = _find_primary_table_bs4(soup)
    if not table:
        return []

    rows = table.find_all("tr")
    if not rows:
        return []

    header_cells = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
    desc_idx = _get_description_index_from_cells(header_cells)
    type_idx = _get_type_index_from_cells(header_cells)
    if desc_idx is None:
        return []

    results: list[tuple[str, str]] = []
    for row in rows[1:]:
        cells = row.find_all("td")
        if len(cells) <= desc_idx:
            continue
        # Extract type_value from Type column (empty string if column missing)
        type_val = ""
        if type_idx is not None and len(cells) > type_idx:
            type_val = cells[type_idx].get_text(strip=True)
        raw = cells[desc_idx].get_text(separator="\n", strip=False)
        for desc in _split_non_empty_lines(raw):
            results.append((type_val, desc))
    return results


def _find_primary_table_bs4(soup: Any) -> Any | None:
    """Prefer rowData table and fall back to first table."""
    return soup.find("table", id="rowData") or soup.find("table")


def _parse_html_descriptions_regex(html: str) -> list[tuple[str, str]]:
    """Parse Type and Description values from Orca Scan HTML using regex fallback."""
    search_html = _row_data_extractor(html)
    header_cells = _extract_header_cells_regex(search_html)
    if not header_cells:
        return []

    desc_idx = _get_description_index_from_cells(header_cells)
    type_idx = _get_type_index_from_cells(header_cells)
    if desc_idx is None:
        return []

    results: list[tuple[str, str]] = []
    all_rows = re.findall(
        r"<tr[^>]*>(.*?)</tr>", search_html, re.DOTALL | re.IGNORECASE
    )
    for row_html in all_rows[1:]:  # skip header
        cells = re.findall(
            r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL | re.IGNORECASE
        )
        normalized_cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        if len(normalized_cells) <= desc_idx or not normalized_cells[desc_idx]:
            continue
        # Extract type_value from Type column (empty string if column missing)
        type_val = ""
        if type_idx is not None and len(normalized_cells) > type_idx:
            type_val = normalized_cells[type_idx]
        for desc in _split_non_empty_lines(normalized_cells[desc_idx]):
            results.append((type_val, desc))
    return results


def _row_data_extractor(html: str) -> str:
    """Return rowData table HTML body when present; otherwise return full HTML."""
    table_match = re.search(
        r'<table[^>]*id=["\']rowData["\'][^>]*>(.*?)</table>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    return table_match.group(1) if table_match else html


def _extract_header_cells_regex(search_html: str) -> list[str]:
    """Extract normalized header cell texts from first row using regex."""
    header_match = re.search(
        r"<tr[^>]*>(.*?)</tr>", search_html, re.DOTALL | re.IGNORECASE
    )
    if not header_match:
        return []

    header_cells = re.findall(
        r"<t[hd][^>]*>(.*?)</t[hd]>", header_match.group(1), re.DOTALL | re.IGNORECASE
    )
    return [re.sub(r"<[^>]+>", "", c).strip() for c in header_cells]


def _get_description_index_from_cells(cells: list[str]) -> int | None:
    """Return Description column index if present in header cells."""
    if "Description" not in cells:
        return None
    return cells.index("Description")


def _get_type_index_from_cells(cells: list[str]) -> int | None:
    """Return Type column index if present in header cells."""
    if "Type" not in cells:
        return None
    return cells.index("Type")


def _extract_location_from_type(type_value: str | None) -> str:
    """
    Extract location suffix (APO or BB) from Type column value.
    
    Format: MMDD + location suffix (e.g., '0420APO' → 'APO', '0420BB' → 'BB')
    Returns the configured LOCATION default if extraction fails.
    """
    if not type_value:
        return LOCATION
    # Extract suffix after 4-digit date prefix
    type_value = type_value.strip()
    if len(type_value) > 4:
        suffix = type_value[4:].upper()
        if suffix in ("APO", "BB"):
            return suffix
    return LOCATION


def _split_non_empty_lines(raw_text: str) -> list[str]:
    """Split text by lines and return only non-empty trimmed lines."""
    return [line.strip() for line in raw_text.splitlines() if line.strip()]


# ─── Parsing & Normalization ─────────────────────────────────────────────────

# not phase based
def parse_descriptions_to_manifest(descriptions: list[tuple[str, str]], email_date: datetime) -> tuple[dict, list[str]]:
    """
    Apply regex to each description string and build a session manifest.

    Scan format: <MVA:8 digits><AREA_ID:uppercase>[r][c]
      r = repair flag (only valid on repair-eligible areas, e.g. WS)
      c = claim listed flag

    On parse error the row is written to the manifest with the error code
    (MALFORMED_SCAN | AMBIGUOUS_LOCATION | INVALID_REPAIR) in the
    Damage Area field and other variable fields blank.  This satisfies
    the Option-A decision: errors land in the sheet for auditor review.

    Args:
        descriptions: List of (type_value, description) tuples from email parsing.
                      type_value is the email Type column (e.g., '0420APO').
        email_date: Email Date header as datetime

    Returns:
        manifest: dict keyed by MVA (or scan string for MALFORMED_SCAN) →
                  {Arrival Date, MVA, FPO#, VIN, Make, Location, Damage Type,
                   Damage Area, Claim#, WorkItem}
        mva_list: list of clean 8-digit MVA strings for the worker (errors excluded)
    """
    log.info("Parsing: Processing %d descriptions …", len(descriptions))

    manifest: dict[str, dict] = {}
    mva_list: list[str] = []
    date_str = email_date.strftime("%m/%d/%Y")
    missing_type_count = 0
    default_work_item = RUNTIME_CONFIG.get("work_item_default_flag", "verified")

    for type_value, desc in descriptions:
        raw = desc.strip()
        location = _extract_location_from_type(type_value)
        if not type_value:
            missing_type_count += 1

        match = MVA_PATTERN.match(raw)
        if not match:
            log.warning("Parsing: MALFORMED_SCAN — scan='%s'", raw)
            continue

        mva = match.group(1)
        area_code = match.group(2)
        repair_flag = match.group(3)   # "r" or ""
        claim_flag = match.group(4)    # "c" or ""

        # Validate area code against config
        if area_code not in AREAS:
            log.warning("Parsing: AMBIGUOUS_LOCATION — scan='%s'", raw)
            continue

        # Repair flag only valid on repair-eligible areas
        if repair_flag and area_code not in REPAIR_ELIGIBLE_AREAS:
            log.warning("Parsing: INVALID_REPAIR — scan='%s'", raw)
            continue

        damage_type = "Repair" if repair_flag else "Replacement"
        damage_area = AREAS[area_code]
        # Claim status values must match allowed UI options.
        claim = "Listed" if claim_flag else "Missing"

        manifest[mva] = {
            "Arrival Date": date_str,
            "MVA": mva,
            "FPO#": "",      # Manually maintained — pipeline writes blank
            "VIN": "",       # Populated during merge step
            "Make": "",      # Populated during merge from GlassResults Desc
            "Location": location,
            "Action": damage_type,
            "Area": damage_area,
            "Claim#": claim,
            "WorkItem": default_work_item,
        }
        mva_list.append(mva)

    if missing_type_count > 0:
        log.warning("Parsing: %d entries missing/empty Type value — using default location '%s'", missing_type_count, LOCATION)
    log.info("Parsing: Manifest built — %d valid MVAs", len(mva_list))
    return manifest, mva_list


def apply_cycle_day_tracking(manifest: dict[str, dict], mva_list: list[str], snapshot_date: datetime) -> None:
    """Update local cycle-day store and annotate manifest rows with cycle metrics."""
    tracker = CycleTracker(
        CYCLE_TRACKER_STORE,
        gap_grace_days=CYCLE_GAP_GRACE_DAYS,
        completed_retention=CYCLE_COMPLETED_RETENTION,
    )
    cycle_days_by_mva = tracker.record_snapshot(mva_list, snapshot_date.date())
    for mva, days in cycle_days_by_mva.items():
        if mva in manifest:
            # Kept out of the Google sheet 8-column contract; useful for metrics tab/reporting.
            manifest[mva]["Cycle Days"] = days
    log.info(
        "Cycle tracking: %d active MVAs recorded (grace=%d day(s))",
        len(cycle_days_by_mva),
        CYCLE_GAP_GRACE_DAYS,
    )


# ─── Worker Processing ────────────────────────────────────────────────────────

# Not phase and make the methods action oriented with names that make sense
def parse_glass_data_results(mva_list: list[str]) -> None:
    """
    Write clean MVAs to the CSV interface file, then invoke the
    external GlassDataParser.py worker as a subprocess.

    Raises subprocess.CalledProcessError on worker failure.
    """
    log.info("Worker: Writing %d MVAs to %s …", len(mva_list), CSV_PATH)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["MVA"])
        for mva in mva_list:
            writer.writerow([mva])

    log.info("Worker: Invoking worker subprocess — %s", WORKER_SCRIPT)
    subprocess.check_call(
        [sys.executable, str(WORKER_SCRIPT)],
        cwd=str(BASE_DIR),
    )
    log.info("Worker: Completed successfully")

# update name to be more ??
def validate_results_freshness(results_path: Path, max_age_seconds: int = 300) -> None:
    """
    Verify that the results file was recently modified (by the current worker run).
    Raises RuntimeError if the file is stale or missing.
    """
    if not results_path.exists():
        raise RuntimeError(f"Results file not found: {results_path}")
    mtime = datetime.fromtimestamp(results_path.stat().st_mtime)
    age = datetime.now() - mtime
    if age > timedelta(seconds=max_age_seconds):
        raise RuntimeError(
            f"Stale results file: {results_path} was last modified "
            f"{age} ago (max allowed: {max_age_seconds}s)"
        )


# ─── Data Reconciliation ──────────────────────────────────────────────────────

# phase...
def merge_manifest_with_results(manifest: dict) -> pd.DataFrame:
    """
    Left-join the session manifest with scraper output
    (GlassResults.txt from worker execution).

    Any scanned MVA without a scraper match keeps VIN='N/A'.
    """
    log.info("Merge: Reconciling manifest with scraper results …")

    # Build manifest DataFrame
    df_manifest = pd.DataFrame(list(manifest.values()))

    # Read scraper results
    if RESULTS_PATH.exists():
        df_results = pd.read_csv(
            RESULTS_PATH,
            sep=",",
            dtype=str,
            encoding="utf-8",
        )
        # Normalize column names
        df_results.columns = [c.strip() for c in df_results.columns]
        # Keep only MVA and VIN (and optionally Desc from scraper)
        result_cols = [c for c in ["MVA", "VIN", "Desc"] if c in df_results.columns]
        df_results = df_results[result_cols]
    else:
        log.warning("Merge: %s not found — all VINs will be N/A", RESULTS_PATH)
        df_results = pd.DataFrame(columns=["MVA", "VIN"])

    # Prepare columns for left join
    join_cols = ["MVA"]
    rename_map = {"VIN": "VIN_scraped"}
    if "Desc" in df_results.columns:
        rename_map["Desc"] = "Make_scraped"
        join_cols.append("Desc")
    join_cols.append("VIN")

    df_merged = df_manifest.merge(
        df_results[join_cols].rename(columns=rename_map),
        on="MVA",
        how="left",
    )

    # Populate VIN: scraped value if available, else 'N/A'
    df_merged["VIN"] = df_merged["VIN_scraped"].fillna("N/A")
    df_merged.drop(columns=["VIN_scraped"], inplace=True)

    # Populate Make from scraped Desc if available
    if "Make_scraped" in df_merged.columns:
        df_merged["Make"] = df_merged["Make_scraped"].fillna(df_merged["Make"])
        df_merged.drop(columns=["Make_scraped"], inplace=True)

    # Ensure column order
    df_merged = df_merged[COLUMNS]

    n_missing = (df_merged["VIN"] == "N/A").sum()
    log.info("Merge: Complete — %d rows, %d missing VINs", len(df_merged), n_missing)
    return df_merged


# ─── Persistence ───────────────────────────────────────────────────────────────


def _get_worksheet():
    """Authenticate with Google Sheets and return the GlassClaims worksheet."""
    if gspread is None:
        raise ModuleNotFoundError(
            "Missing dependency 'gspread'. Use the project virtual environment: "
            "'.venv\\Scripts\\python.exe GlassOrchestrator.py' "
            "or run 'Run-GlassOrchestrator.cmd'."
        )

    gc = gspread.service_account(filename=str(SERVICE_ACCOUNT_JSON))
    sh = gc.open_by_key(SPREADSHEET_ID)
    return sh.worksheet(SHEET_NAME)

# phase.. Not descriptive
# validating mva's and arrival date does not add a lot of values.  MVA are 
# guarrentteed to be unique and we only perform this process once per day.  
#im questioning the value of confirming mva/date
# we might want to break this method up into multiple additional methods:
# FindLatestRow()
# InsertNewRow()
def persist_new_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Append merged data to Google Sheet 'ATL_Data 2026 : GlassClaims'.

    Inserts new rows above the summary section so formulas stay intact.
    Idempotency: Composite key (MVA + Arrival Date) is checked against
    existing rows. Duplicate rows are silently skipped.

    Returns the DataFrame of actually-new rows written.
    """
    log.info("Persistence: Appending to Google Sheet [%s] …", SHEET_NAME)

    ws = _get_worksheet()

    # Determine which rows are truly new
    existing_keys = _load_existing_keys(ws)
    new_rows = _filter_new_rows(df, existing_keys)

    if new_rows.empty:
        log.info("Persistence: No new rows to write (all duplicates)")
        return new_rows

    # Find the insertion point: first empty row after last data row (column B = MVA)
    insert_row = _find_insert_row(ws)

    # Build rows as lists matching the 8-column contract
    rows_to_insert = _rows_from_dataframe(new_rows)

    # Insert rows above the summary section (pushes summary down automatically).
    # inherit_from_before=True: new rows inherit formatting from the data row above,
    # not the summary row below (which is orange/bold and would corrupt the inserted rows).
    ws.insert_rows(rows_to_insert, row=insert_row, inherit_from_before=True)

    log.info("Persistence: Wrote %d new rows to Google Sheet at row %d", len(new_rows), insert_row)
    return new_rows


def _filter_new_rows(df: pd.DataFrame, existing_keys: set[str]) -> pd.DataFrame:
    """Return only rows not already present in the sheet (MVA|Arrival Date key)."""
    df_with_keys = df.assign(_key=df["MVA"] + "|" + df["Arrival Date"])
    return df_with_keys[~df_with_keys["_key"].isin(existing_keys)].drop(columns=["_key"]).copy()


def _find_insert_row(ws) -> int:
    """Return the first row after existing data where new rows should be inserted."""
    all_vals = ws.get_all_values()
    insert_row = 2  # default: right after header
    for i, row in enumerate(all_vals):
        if len(row) > 1 and row[1].strip():  # column B has MVA
            insert_row = i + 2  # next row (1-indexed)
    return insert_row


def _rows_from_dataframe(df: pd.DataFrame) -> list[list[str]]:
    """Build sheet row payloads in the canonical column order.

    Action is mapped to its vendor label (e.g. 'Repair' →
    'Repair(SuperGlass)') via VENDOR_LABELS before writing.  Internal
    pipeline logic always uses the short form; the sheet receives the
    display form.
    """
    rows = []
    for _, row in df.iterrows():
        values = []
        for col in COLUMNS:
            val = row[col]
            if col == "Action":
                val = VENDOR_LABELS.get(str(val), val)
            values.append(val)
        rows.append(values)
    return rows


def _load_existing_keys(ws) -> set[str]:
    """
    Read existing MVA|Date composite keys from the Google Sheet worksheet
    for idempotency checking.
    """
    existing_keys: set[str] = set()
    try:
        all_vals = ws.get_all_values()
        if not all_vals:
            return existing_keys
        headers = all_vals[0]
        mva_idx = headers.index("MVA") if "MVA" in headers else None
        date_idx = headers.index("Arrival Date") if "Arrival Date" in headers else None
        if mva_idx is None or date_idx is None:
            return existing_keys
        for row in all_vals[1:]:
            if len(row) > max(mva_idx, date_idx) and row[mva_idx].strip():
                mva = row[mva_idx].strip()
                arrival_date = row[date_idx].strip()
                key = f"{mva}|{arrival_date}"
                existing_keys.add(key)
    except (AttributeError, KeyError, TypeError, ValueError, OSError) as exc:
        log.warning("Could not read existing sheet data — %s", exc)
        #This is a major problem and breaks the entire flow
    return existing_keys


def is_duplicate(mva: str, date: str, existing_keys: set[str]) -> bool:
    """Return True if the MVA+Date composite key already exists."""
    return f"{mva}|{date}" in existing_keys


# ─── Notification ─────────────────────────────────────────────────────────────


def notify_order_items(df: pd.DataFrame) -> None:
    """
    Build an HTML email with a styled table for all persisted rows,
    and send it. Rows with VIN='N/A' are highlighted red to flag the
    ordering team for manual action.
    """
    log.info("Notification: Building order alert …")

    items = df.copy()
    if items.empty:
        log.info("Notification: No items to notify — skipping")
        return

    html = _build_html_table(items)
    subject = f"Glass Order — {items.iloc[0]['Arrival Date']} ({len(items)} items)"
    outbound = OutboundEmail(
        subject=subject,
        html_body=html,
        sender=SENDER_ADDRESS,
        recipients=NOTIFY_RECIPIENTS,
    )
    _send_email(outbound)
    log.info("Notification: Sent to %s", NOTIFY_RECIPIENTS)


def _build_html_table(df: pd.DataFrame) -> str:
    """Render a DataFrame to an HTML table with red highlighting for N/A VINs."""
    has_missing = (df["VIN"] == "N/A").any()

    rows_html = ""
    for _, row in df.iterrows():
        if row["VIN"] == "N/A":
            style = ' style="background-color:#ff4444; color:#ffffff; font-weight:bold;"'
            vin_cell = (
                '<td style="background-color:#ff0000; color:#ffffff; font-weight:bold;">'
                '⚠ N/A — ACTION REQUIRED</td>'
            )
        else:
            style = ""
            vin_cell = f"<td>{row['VIN']}</td>"

        rows_html += f"""<tr{style}>
            <td>{row['Arrival Date']}</td>
            <td>{row['MVA']}</td>
            {vin_cell}
            <td>{row['Make']}</td>
            <td>{row['Location']}</td>
            <td>{VENDOR_LABELS.get(str(row['Action']), row['Action'])}</td>
            <td>{row['Area']}</td>
            <td>{row['Claim#']}</td>
            <td>{row['WorkItem']}</td>
        </tr>\n"""

    alert_banner = ""
    if has_missing:
        alert_banner = """
        <div style="background-color:#ff4444; color:#ffffff; padding:12px;
                    font-size:16px; font-weight:bold; margin-bottom:16px;
                    border-radius:4px; text-align:center;">
            ⚠ ATTENTION: One or more VINs could not be retrieved.
            Rows highlighted in RED require manual lookup before ordering.
        </div>
        """

    return f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 16px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th {{ background-color: #333; color: #fff; padding: 10px; text-align: left; }}
            td {{ border: 1px solid #ddd; padding: 8px; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
        </style>
    </head>
    <body>
        <h2>Glass Order Summary</h2>
        {alert_banner}
        <table>
            <thead>
                <tr>
                    <th>Arrival Date</th><th>MVA</th><th>VIN</th>
                    <th>Make</th><th>Location</th>
                    <th>Action</th><th>Area</th><th>Claim#</th><th>WorkItem</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        <p style="margin-top:16px; font-size:12px; color:#888;">
            Generated by GlassOrchestrator &mdash; {datetime.now().strftime('%Y-%m-%d %H:%M')}
        </p>
    </body>
    </html>
    """


def _send_email(message: OutboundEmail) -> None:
    """Send an outbound HTML email via Gmail SMTP."""
    if not message.sender or not message.recipients:
        log.warning("Notification: Email credentials not configured — printing subject only")
        log.info("Subject: %s", message.subject)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = message.subject
    msg["From"] = message.sender
    msg["To"] = ", ".join(message.recipients)
    msg.attach(MIMEText(message.html_body, "html"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        server.sendmail(message.sender, message.recipients, msg.as_string())


# ─── Pipeline Orchestrator ────────────────────────────────────────────────────


def run_pipeline() -> None:
    """Execute the end-to-end pipeline with step-level error handling."""
    # Broad exception handling is intentional here to fail-fast by stage
    # while preserving a stable top-level orchestrator process.
    # pylint: disable=broad-exception-caught
    log.info("=" * 60)
    log.info("GlassOrchestrator pipeline starting")
    log.info("=" * 60)

    # Step 1: Input acquisition
    try:
        descriptions, email_date = fetch_input_descriptions()
    except Exception as exc:
        log.error("Input acquisition failed — %s", exc, exc_info=True)
        return

    if not descriptions:
        log.info("Pipeline complete — no descriptions to process")
        return

    # Step 2: Parsing
    try:
        manifest, mva_list = parse_descriptions_to_manifest(descriptions, email_date)
    except Exception as exc:
        log.error("Parsing failed — %s", exc, exc_info=True)
        return

    if not manifest:
        log.info("Pipeline complete — no valid MVAs after parsing")
        return

    # Step 2b: Cycle-day tracking (local JSON state)
    try:
        apply_cycle_day_tracking(manifest, mva_list, email_date)
    except Exception as exc:
        # Tracking should not block operational processing.
        log.error("Cycle tracking failed — %s", exc, exc_info=True)

    # Step 3: Worker
    try:
        parse_glass_data_results(mva_list)
    except subprocess.CalledProcessError as exc:
        log.error("Worker failed — non-zero exit code %d. "
                   "Pipeline ABORTED. No data will be persisted.", exc.returncode)
        return
    except Exception as exc:
        log.error("Worker failed — %s. Pipeline ABORTED.", exc, exc_info=True)
        return

    # Step 4: Validate worker output freshness
    try:
        validate_results_freshness(RESULTS_PATH)
    except RuntimeError as exc:
        log.error("Worker output validation failed — %s. Pipeline ABORTED.", exc)
        return

    # Step 5: Merge
    try:
        df_merged = merge_manifest_with_results(manifest)
    except Exception as exc:
        log.error("Merge failed — %s", exc, exc_info=True)
        return

    # Step 6: Persist
    try:
        df_new_rows = persist_new_rows(df_merged)
        log.info("Persistence: %d new row(s) written", len(df_new_rows))
    except Exception as exc:
        log.error("Persistence failed — %s", exc, exc_info=True)
        return

    # Step 7: Notify
    try:
        from core.eligibility import is_notification_eligible
        eligible_rows = df_new_rows[df_new_rows.apply(lambda r: is_notification_eligible(r.to_dict()), axis=1)]
        notify_order_items(eligible_rows)
    except Exception as exc:
        log.error("Notification failed — %s", exc, exc_info=True)
        # Notification failure is non-fatal for data persistence; pipeline ends here
        return

    log.info("=" * 60)
    log.info("GlassOrchestrator pipeline completed successfully")
    log.info("=" * 60)


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_pipeline()
