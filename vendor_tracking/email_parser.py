"""AutoGlassNow email parsing for vendor lifecycle tracking.

Handles three inbound email types:
  1. Appointment confirmation — seeds JobId via Zeta VIEW STATUS href
  2. Approval-needed quote   — vendor blocked; extracts VIN, cost, ETA
  3. Technician-assigned     — status update only; no VIN expected

Classification is done by sender + subject + body keyword heuristics.
All parsing is best-effort; missing fields are returned as None.
"""

import base64
import email as email_module
import email.message
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False


# ─── Email type classification ────────────────────────────────────────────────

class EmailType(Enum):
    APPOINTMENT_CONFIRMATION = auto()
    APPROVAL_NEEDED = auto()
    TECHNICIAN_ASSIGNED = auto()
    COMPLETION_RECEIPT = auto()
    UNKNOWN = auto()


# Known AutoGlassNow sender domains and subject / body fingerprints.
_APPOINTMENT_SUBJECTS = [
    "thank you for scheduling",
    "appointment confirmed",
    "your service is scheduled",
]
_APPOINTMENT_BODY_CUES = [
    "thank you for scheduling your service",
    "view status",
    "e.e.autoglassnow.com/click",
]
_APPROVAL_SUBJECTS = [
    "please advise",
]
_APPROVAL_BODY_CUES = [
    "please advise",
    "prior approval",
    "adas calibration",
    "approval required",
]
_TECH_ASSIGNED_SUBJECTS = [
    "we've assigned your tech",
    "certified technician has been assigned",
    "technician assigned",
    "tech has been assigned",
]
_TECH_ASSIGNED_BODY_CUES = [
    "your certified technician has been assigned",
    "technician has been assigned",
]
_COMPLETION_SUBJECTS = [
    "receipt for job #",
    "receipt for job#",
    "glass receipt",
    "repair receipt",
]
_AGN_SENDER_DOMAINS = ["autoglassnow.com", "omegaedi.com"]


def classify_email(msg: email_module.message.Message) -> EmailType:
    """Classify an inbound AutoGlassNow email by sender + subject + body cues."""
    sender = str(msg.get("From", "")).lower()
    subject = str(msg.get("Subject", "")).lower()

    # Gate on known AutoGlassNow sender domains
    if not any(domain in sender for domain in _AGN_SENDER_DOMAINS):
        return EmailType.UNKNOWN

    # Completion receipt
    if any(cue in subject for cue in _COMPLETION_SUBJECTS):
        return EmailType.COMPLETION_RECEIPT

    # Technician assigned
    if any(cue in subject for cue in _TECH_ASSIGNED_SUBJECTS):
        return EmailType.TECHNICIAN_ASSIGNED

    # Approval needed — subject match first, then body scan
    if any(cue in subject for cue in _APPROVAL_SUBJECTS):
        return EmailType.APPROVAL_NEEDED

    # Appointment confirmation
    if any(cue in subject for cue in _APPOINTMENT_SUBJECTS):
        return EmailType.APPOINTMENT_CONFIRMATION

    # Fall back to body scan if subject was inconclusive
    body = _get_message_body(msg).lower()
    if any(cue in body for cue in _APPOINTMENT_BODY_CUES):
        return EmailType.APPOINTMENT_CONFIRMATION
    if any(cue in body for cue in _APPROVAL_BODY_CUES):
        return EmailType.APPROVAL_NEEDED
    if any(cue in body for cue in _TECH_ASSIGNED_BODY_CUES):
        return EmailType.TECHNICIAN_ASSIGNED

    return EmailType.UNKNOWN


# ─── Result dataclasses ───────────────────────────────────────────────────────

@dataclass
class AppointmentEmailData:
    """Fields extracted from an AutoGlassNow appointment confirmation email."""
    job_id: Optional[str]           # Numeric JobId from VIEW STATUS href
    tracker_url: Optional[str]      # https://www.autoglassnow.com/job-tracker/<job_id>/
    appointment_date: Optional[str] # e.g. "05/06/2026"
    service_type: Optional[str]     # e.g. "Windshield Replacement"
    vehicle: Optional[str]          # e.g. "2026 Gmc Terrain"
    location: Optional[str]         # Service address


@dataclass
class ApprovalNeededEmailData:
    """Fields extracted from an AutoGlassNow approval-needed email."""
    vin: Optional[str]              # 17-char VIN
    quoted_cost: Optional[str]      # e.g. "$450.00"
    eta_notes: Optional[str]        # Free-text ETA or delivery note
    work_order_ref: Optional[str]   # Quote # or Work Order # when present


@dataclass
class TechnicianAssignedEmailData:
    """Fields extracted from a technician-assigned notice."""
    assigned_date: Optional[str]    # e.g. "05/06/2026"
    tracker_url: Optional[str]


# ─── JobId / Zeta href extraction ────────────────────────────────────────────

def extract_job_id_from_zeta_href(href: str) -> Optional[str]:
    """Extract AutoGlassNow JobId from a Zeta email tracking redirect href.

    The href format is:
        https://e.e.autoglassnow.com/click/<seg1>/<seg2>/...

    Each path segment is:  <1-char prefix> + <base64url-encoded data>
    The segment whose prefix is 'V', when prefix-stripped and base64-decoded,
    yields a URL like https://www.autoglassnow.com/job-tracker/<JobId>/

    Returns the numeric JobId string, or None if extraction fails.
    """
    for segment in href.split("/"):
        if not segment or len(segment) < 2:
            continue
        if segment[0] != "V":
            continue
        encoded = segment[1:]
        # Pad to a valid base64 length
        padded = encoded + "=" * ((4 - len(encoded) % 4) % 4)
        try:
            decoded = base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
        except Exception:
            continue
        match = re.search(r"autoglassnow\.com/job-tracker/(\d+)", decoded)
        if match:
            return match.group(1)
    return None


def _find_view_status_href(html: str) -> Optional[str]:
    """Return the href of the VIEW STATUS anchor in appointment email HTML."""
    if _HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href: str = anchor["href"]
            if "e.e.autoglassnow.com/click" in href:
                return href
            text = anchor.get_text(strip=True).upper()
            if "VIEW STATUS" in text and href.startswith("http"):
                return href
    else:
        # Regex fallback
        m = re.search(r'href=["\']([^"\']*e\.e\.autoglassnow\.com/click[^"\']*)["\']', html, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


# ─── Appointment confirmation parsing ────────────────────────────────────────

_DATE_PATTERNS = [
    re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b"),
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    re.compile(
        r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
        r"(\w+ \d{1,2},\s+\d{4})\b",
        re.IGNORECASE,
    ),
]

_SERVICE_TYPES = [
    "Windshield Replacement",
    "Windshield Repair",
    "Side Window Replacement",
    "Back Window Replacement",
    "Sunroof Replacement",
    "ADAS Calibration",
]


def _extract_first_date(text: str) -> Optional[str]:
    for pattern in _DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(1)
    return None


def _extract_service_type(text: str) -> Optional[str]:
    for svc in _SERVICE_TYPES:
        if svc.lower() in text.lower():
            return svc
    # Generic fallback: look for "Replacement" or "Repair" near "Windshield" etc.
    m = re.search(
        r"(Windshield|Side Window|Back Window|Sunroof)\s+(Replacement|Repair)",
        text, re.IGNORECASE,
    )
    if m:
        return f"{m.group(1).title()} {m.group(2).title()}"
    return None


def _extract_vehicle(text: str) -> Optional[str]:
    """Extract a Year Make Model string (e.g. '2026 Gmc Terrain')."""
    m = re.search(r"\b(20\d{2})\s+([A-Z][a-z]+(?: [A-Z][a-z0-9]+)+)\b", text)
    if m:
        return m.group(0)
    return None


def _extract_location_address(text: str) -> Optional[str]:
    """Heuristic: find a street address line (number + street name)."""
    m = re.search(r"\b(\d+\s+[A-Za-z0-9 ,.#]+(?:St|Ave|Blvd|Rd|Dr|Ln|Way|Court|Ct|Place|Pl)\.?)\b", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def parse_appointment_email(html: str) -> AppointmentEmailData:
    """Parse an AutoGlassNow appointment confirmation email HTML body."""
    href = _find_view_status_href(html)
    job_id: Optional[str] = None
    tracker_url: Optional[str] = None
    if href:
        job_id = extract_job_id_from_zeta_href(href)
        if job_id:
            tracker_url = f"https://www.autoglassnow.com/job-tracker/{job_id}/"

    # Strip HTML for field extraction
    if _HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n")
    else:
        text = re.sub(r"<[^>]+>", " ", html)

    return AppointmentEmailData(
        job_id=job_id,
        tracker_url=tracker_url,
        appointment_date=_extract_first_date(text),
        service_type=_extract_service_type(text),
        vehicle=_extract_vehicle(text),
        location=_extract_location_address(text),
    )


# ─── Approval-needed parsing ──────────────────────────────────────────────────

def normalize_vin(raw: str) -> str:
    """Normalize a raw VIN string: uppercase, strip non-alphanumeric, require 17 chars."""
    normalized = re.sub(r"[^A-Z0-9]", "", raw.upper())
    return normalized if len(normalized) == 17 else ""


def _extract_vin_from_text(text: str) -> Optional[str]:
    """Extract the first valid 17-character VIN from plain text."""
    # Labeled: "VIN: 1HGBH41JXMN109186" or "VIN# ..."
    m = re.search(r"\bVIN[:#\s]+([A-HJ-NPR-Z0-9]{17})\b", text, re.IGNORECASE)
    if m:
        candidate = normalize_vin(m.group(1))
        if candidate:
            return candidate

    # Unlabeled 17-char VIN on its own
    for candidate in re.findall(r"\b([A-HJ-NPR-Z0-9]{17})\b", text, re.IGNORECASE):
        normalized = normalize_vin(candidate)
        if normalized:
            return normalized
    return None


def _extract_cost_from_text(text: str) -> Optional[str]:
    """Extract a dollar-amount string (e.g. '$450.00')."""
    # Prefer "Total:" labelled amount
    m = re.search(r"Total[:\s]+\$?([\d,]+\.\d{2})", text, re.IGNORECASE)
    if m:
        return f"${m.group(1)}"
    # Any standalone dollar amount
    m = re.search(r"\$\s*([\d,]+\.\d{2})", text)
    if m:
        return f"${m.group(1)}"
    return None


def _extract_eta_from_text(text: str) -> Optional[str]:
    """Extract ETA note text following an ETA label."""
    m = re.search(r"ETA[:\s]+(.+?)(?:\n|$)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def _extract_work_order_ref(text: str) -> Optional[str]:
    """Extract a Quote # or Work Order # reference."""
    m = re.search(r"(?:Quote|Work Order|WO|Job)[#\s:]+(\w+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def parse_approval_needed_email(html: str) -> ApprovalNeededEmailData:
    """Parse an AutoGlassNow approval-needed email HTML body."""
    if _HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n")
    else:
        text = re.sub(r"<[^>]+>", " ", html)

    vin_raw = _extract_vin_from_text(text) or ""
    vin = normalize_vin(vin_raw) if vin_raw else None

    return ApprovalNeededEmailData(
        vin=vin or None,
        quoted_cost=_extract_cost_from_text(text),
        eta_notes=_extract_eta_from_text(text),
        work_order_ref=_extract_work_order_ref(text),
    )


# ─── Technician-assigned parsing ─────────────────────────────────────────────

def parse_technician_assigned_email(html: str) -> TechnicianAssignedEmailData:
    """Parse an AutoGlassNow technician-assigned notice HTML body."""
    href = _find_view_status_href(html)
    tracker_url: Optional[str] = None
    if href:
        job_id = extract_job_id_from_zeta_href(href)
        if job_id:
            tracker_url = f"https://www.autoglassnow.com/job-tracker/{job_id}/"

    if _HAS_BS4:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n")
    else:
        text = re.sub(r"<[^>]+>", " ", html)

    return TechnicianAssignedEmailData(
        assigned_date=_extract_first_date(text),
        tracker_url=tracker_url,
    )


# ─── MIME body helpers ────────────────────────────────────────────────────────

def _get_message_body(msg: email_module.message.Message) -> str:
    """Walk MIME parts and return best body text for classification."""
    html_body = ""
    text_body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            if content_type == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html_body = payload.decode(charset, errors="replace")
            elif content_type == "text/plain" and not html_body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    text_body = payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                html_body = content
            else:
                text_body = content

    return html_body or text_body


def get_html_body(msg: email_module.message.Message) -> str:
    """Return the HTML body of a MIME message (or plain text if no HTML part)."""
    html_body = ""
    text_body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            if content_type == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html_body = payload.decode(charset, errors="replace")
                    break
            elif content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    text_body = payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                html_body = content
            else:
                text_body = content

    return html_body or text_body
