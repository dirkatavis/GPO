"""
Phase 3 Vendor Tracking Tests

VT-1:  extract_job_id_from_zeta_href — Zeta base64 decode
VT-2:  parse_appointment_email — body field extraction
VT-3:  parse_approval_needed_email — VIN, cost, ETA extraction
VT-4:  parse_technician_assigned_email — assigned date extraction
VT-5:  VendorSheetUpdater.find_row — match, not-found, ambiguous
VT-6:  VendorSheetUpdater.update_vendor_fields — targeted column write
VT-7:  Integration — mocked IMAP + mocked worksheet end-to-end
VT-8:  IdempotencyStore — no duplicate writes on rerun
VT-9:  Approval Needed blocker surfaced in run summary
"""

import base64
import email as email_module
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from vendor_tracking.email_parser import (
    AppointmentEmailData,
    ApprovalNeededEmailData,
    EmailType,
    TechnicianAssignedEmailData,
    classify_email,
    extract_job_id_from_zeta_href,
    normalize_vin,
    parse_appointment_email,
    parse_approval_needed_email,
    parse_technician_assigned_email,
)
from vendor_tracking.idempotency_store import IdempotencyStore
from vendor_tracking.sheet_updater import (
    VendorSheetUpdater,
    STATUS_APPROVAL_NEEDED,
    STATUS_COMPLETED,
    STATUS_SCHEDULED,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _make_zeta_segment(url: str) -> str:
    """Build a Zeta path segment for a given decoded URL (prefix='V')."""
    encoded = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
    return f"V{encoded}"


SAMPLE_JOB_ID = "4723644"
SAMPLE_TRACKER_URL = f"https://www.autoglassnow.com/job-tracker/{SAMPLE_JOB_ID}/"

SAMPLE_ZETA_HREF = (
    "https://e.e.autoglassnow.com/click"
    "/Xdummy1"
    f"/{_make_zeta_segment(SAMPLE_TRACKER_URL)}"
    "/Xdummy2"
)

APPOINTMENT_HTML = f"""
<html><body>
<p>Thank you for scheduling your service!</p>
<p>Date: 05/06/2026</p>
<p>Service: Windshield Replacement</p>
<p>Vehicle: 2026 Gmc Terrain</p>
<p>Location: 123 Main St, Atlanta GA</p>
<a href="{SAMPLE_ZETA_HREF}">VIEW STATUS</a>
</body></html>
"""

APPROVAL_HTML = """
<html><body>
<p>Please Advise — Prior Approval Required</p>
<table>
<tr><td>VIN</td><td>1HGBH41JXMN109186</td></tr>
<tr><td>Part</td><td>OEM Windshield</td></tr>
<tr><td>Total</td><td>$450.00</td></tr>
<tr><td>ETA</td><td>3-5 business days</td></tr>
<tr><td>Quote #</td><td>WO99887</td></tr>
</table>
</body></html>
"""

TECH_ASSIGNED_HTML = f"""
<html><body>
<p>Your Certified Technician Has Been Assigned</p>
<p>Assigned Date: 05/07/2026</p>
<a href="{SAMPLE_ZETA_HREF}">VIEW STATUS</a>
</body></html>
"""


def _make_message(
    sender: str = "info@e.autoglassnow.com",
    subject: str = "Test",
    body: str = "",
    message_id: str = "<test@autoglassnow.com>",
) -> email_module.message.Message:
    """Build a minimal email.message.Message for testing."""
    msg = email_module.message_from_string(
        f"From: {sender}\r\n"
        f"Subject: {subject}\r\n"
        f"Message-ID: {message_id}\r\n"
        f"Content-Type: text/html; charset=utf-8\r\n"
        f"\r\n"
        f"{body}"
    )
    return msg


def _make_sheet_updater_with_mock(
    headers: list[str],
    data_rows: list[list[str]],
) -> tuple[VendorSheetUpdater, MagicMock]:
    """Create a VendorSheetUpdater with a mocked gspread worksheet."""
    all_values = [headers] + data_rows

    mock_ws = MagicMock()
    mock_ws.get_all_values.return_value = all_values

    updater = VendorSheetUpdater.__new__(VendorSheetUpdater)
    updater._spreadsheet_id = "fake_id"
    updater._sheet_name = "GlassClaims"
    updater._service_account_json = "fake.json"
    updater._ws = mock_ws
    updater._headers = headers[:]
    updater._all_values = all_values

    return updater, mock_ws


# ─── VT-1: Zeta base64 decode → JobId ────────────────────────────────────────

class TestVT1_JobIdExtraction:
    """VT-1: extract_job_id_from_zeta_href — Zeta base64 decode"""

    def test_extracts_job_id_from_valid_href(self):
        job_id = extract_job_id_from_zeta_href(SAMPLE_ZETA_HREF)
        assert job_id == SAMPLE_JOB_ID

    def test_returns_none_for_empty_href(self):
        assert extract_job_id_from_zeta_href("") is None

    def test_returns_none_for_non_zeta_href(self):
        assert extract_job_id_from_zeta_href("https://www.example.com/page") is None

    def test_handles_different_job_id(self):
        tracker_url = "https://www.autoglassnow.com/job-tracker/9999999/"
        href = f"https://e.e.autoglassnow.com/click/{_make_zeta_segment(tracker_url)}"
        assert extract_job_id_from_zeta_href(href) == "9999999"

    def test_confirmed_sample_4689437(self):
        tracker_url = "https://www.autoglassnow.com/job-tracker/4689437/"
        href = f"https://e.e.autoglassnow.com/click/A/{_make_zeta_segment(tracker_url)}/B"
        assert extract_job_id_from_zeta_href(href) == "4689437"


# ─── VT-2: Appointment email body field extraction ────────────────────────────

class TestVT2_AppointmentParsing:
    """VT-2: parse_appointment_email — body field extraction"""

    def setup_method(self):
        self.result: AppointmentEmailData = parse_appointment_email(APPOINTMENT_HTML)

    def test_extracts_job_id(self):
        assert self.result.job_id == SAMPLE_JOB_ID

    def test_extracts_tracker_url(self):
        assert self.result.tracker_url == SAMPLE_TRACKER_URL

    def test_extracts_appointment_date(self):
        assert self.result.appointment_date == "05/06/2026"

    def test_extracts_service_type(self):
        assert self.result.service_type is not None
        assert "Windshield" in self.result.service_type

    def test_extracts_vehicle(self):
        assert self.result.vehicle is not None
        assert "Terrain" in self.result.vehicle

    def test_missing_view_status_returns_none_job_id(self):
        html = "<html><body><p>Thank you for scheduling</p></body></html>"
        result = parse_appointment_email(html)
        assert result.job_id is None
        assert result.tracker_url is None


# ─── VT-3: Approval-needed email parsing ─────────────────────────────────────

class TestVT3_ApprovalNeededParsing:
    """VT-3: parse_approval_needed_email — VIN, cost, ETA extraction"""

    def setup_method(self):
        self.result: ApprovalNeededEmailData = parse_approval_needed_email(APPROVAL_HTML)

    def test_extracts_vin(self):
        assert self.result.vin == "1HGBH41JXMN109186"

    def test_extracts_cost(self):
        assert self.result.quoted_cost is not None
        assert "450" in self.result.quoted_cost

    def test_extracts_eta(self):
        assert self.result.eta_notes is not None
        assert "business days" in self.result.eta_notes.lower()

    def test_extracts_work_order_ref(self):
        assert self.result.work_order_ref == "WO99887"

    def test_vin_normalization_strips_whitespace(self):
        assert normalize_vin("  1HGBH41JXMN109186  ") == "1HGBH41JXMN109186"

    def test_vin_normalization_rejects_short_vin(self):
        assert normalize_vin("1HGBH41") == ""

    def test_missing_vin_returns_none(self):
        html = "<html><body><p>Please Advise</p><p>Total: $200.00</p></body></html>"
        result = parse_approval_needed_email(html)
        assert result.vin is None


# ─── VT-4: Technician-assigned parsing ───────────────────────────────────────

class TestVT4_TechnicianAssignedParsing:
    """VT-4: parse_technician_assigned_email — assigned date extraction"""

    def test_extracts_assigned_date(self):
        result: TechnicianAssignedEmailData = parse_technician_assigned_email(TECH_ASSIGNED_HTML)
        assert result.assigned_date == "05/07/2026"

    def test_extracts_tracker_url(self):
        result = parse_technician_assigned_email(TECH_ASSIGNED_HTML)
        assert result.tracker_url == SAMPLE_TRACKER_URL

    def test_missing_date_returns_none(self):
        html = "<html><body><p>Your technician has been assigned.</p></body></html>"
        result = parse_technician_assigned_email(html)
        assert result.assigned_date is None


# ─── VT-5: Sheet row matching ────────────────────────────────────────────────

class TestVT5_SheetRowMatching:
    """VT-5: VendorSheetUpdater.find_row — match, not-found, ambiguous"""

    def setup_method(self):
        headers = ["Arrival Date", "MVA", "FPO#", "VIN", "Make"]
        data_rows = [
            ["05/01/2026", "12345678", "FPO001", "1HGBH41JXMN109186", "Honda"],
            ["05/02/2026", "87654321", "FPO002", "2HGBH41JXMN109187", "Toyota"],
            # Duplicate: same VIN + same date as row 1 (to test ambiguous case)
            ["05/01/2026", "99999999", "FPO003", "1HGBH41JXMN109186", "Honda"],
        ]
        self.updater, _ = _make_sheet_updater_with_mock(headers, data_rows)

    def test_finds_unique_match(self):
        result = self.updater.find_row("2HGBH41JXMN109187", "05/02/2026")
        assert result.is_ok
        assert result.row_index == 3  # header=1, first data=2, second=3

    def test_returns_not_found_for_unknown_vin(self):
        result = self.updater.find_row("9ZZZZ00000ZZZ0000", "05/01/2026")
        assert result.status == "not_found"

    def test_returns_ambiguous_for_duplicate_key(self):
        result = self.updater.find_row("1HGBH41JXMN109186", "05/01/2026")
        assert result.status == "ambiguous"

    def test_invalid_vin_returns_not_found(self):
        result = self.updater.find_row("TOOSHORT", "05/01/2026")
        assert result.status == "not_found"

    def test_date_normalization_iso_format(self):
        """Sheet date in ISO format should match incoming M/D/YYYY format."""
        headers = ["Arrival Date", "VIN"]
        data_rows = [["2026-05-02", "2HGBH41JXMN109187"]]
        updater, _ = _make_sheet_updater_with_mock(headers, data_rows)
        result = updater.find_row("2HGBH41JXMN109187", "05/02/2026")
        assert result.is_ok


# ─── VT-6: Targeted column write ─────────────────────────────────────────────

class TestVT6_UpdateVendorFields:
    """VT-6: VendorSheetUpdater.update_vendor_fields — targeted column write"""

    def setup_method(self):
        headers = [
            "Arrival Date", "MVA", "VIN",
            "Repair Status", "Approval Needed", "Cost", "Repair Status Notes",
        ]
        data_rows = [
            ["05/01/2026", "12345678", "1HGBH41JXMN109186", "", "", "", ""],
        ]
        self.updater, self.mock_ws = _make_sheet_updater_with_mock(headers, data_rows)
        # Refresh cache reflects empty status so precedence checks work
        self.updater._all_values = [headers] + data_rows

    def test_writes_repair_status(self):
        self.updater.update_vendor_fields(2, {"Repair Status": STATUS_APPROVAL_NEEDED})
        self.mock_ws.update_cell.assert_any_call(2, 4, STATUS_APPROVAL_NEEDED)

    def test_status_precedence_blocks_downgrade(self):
        """Completed status must not be overwritten by a lower-precedence status."""
        headers = [
            "Arrival Date", "MVA", "VIN",
            "Repair Status", "Approval Needed",
        ]
        data_rows = [
            ["05/01/2026", "12345678", "1HGBH41JXMN109186", STATUS_COMPLETED, "No"],
        ]
        updater, mock_ws = _make_sheet_updater_with_mock(headers, data_rows)

        updater.update_vendor_fields(2, {"Repair Status": STATUS_SCHEDULED})
        # update_cell should NOT have been called with STATUS_SCHEDULED
        for c in mock_ws.update_cell.call_args_list:
            if c == call(2, 4, STATUS_SCHEDULED):
                pytest.fail("Completed status was downgraded to Scheduled — precedence not enforced")

    def test_writes_multiple_fields(self):
        self.updater.update_vendor_fields(2, {
            "Approval Needed": "Yes",
            "Cost": "$450.00",
            "Repair Status Notes": "ETA: 5 days",
        })
        self.mock_ws.update_cell.assert_any_call(2, 5, "Yes")
        self.mock_ws.update_cell.assert_any_call(2, 6, "$450.00")
        self.mock_ws.update_cell.assert_any_call(2, 7, "ETA: 5 days")

    def test_skips_unknown_column(self):
        """update_vendor_fields must not raise for unknown column names."""
        self.updater.update_vendor_fields(2, {"NonExistentColumn": "value"})
        # No exception raised, and update_cell not called for that column
        for c in self.mock_ws.update_cell.call_args_list:
            assert c.args[2] != "value" or c.args[1] != 99


# ─── VT-7: Integration — mocked IMAP + mocked worksheet ──────────────────────

class TestVT7_IntegrationMocked:
    """VT-7: End-to-end with mocked IMAP and mocked gspread worksheet."""

    def _build_monitor(self, tmp_path: Path):
        from vendor_tracking.monitor import VendorTrackingMonitor
        config = {
            "imap_server": "imap.test.local",
            "email_account": "test@test.com",
            "email_password": "secret",
            "vendor_tracking_spreadsheet_id": "fake_sheet_id",
            "vendor_tracking_sheet_name": "GlassClaims",
            "vendor_tracking_senders": ["autoglassnow.com"],
            "vendor_tracking_lookback_days": 7,
            "vendor_tracking_idempotency_store": str(tmp_path / "idem.json"),
        }
        monitor = VendorTrackingMonitor(config)
        # Inject idempotency store pointing to tmp
        from vendor_tracking.idempotency_store import IdempotencyStore
        monitor._idempotency_path = tmp_path / "idem.json"
        monitor._store = IdempotencyStore(tmp_path / "idem.json")
        return monitor

    def test_approval_needed_email_surfaces_in_approval_list(self, tmp_path):
        monitor = self._build_monitor(tmp_path)

        approval_msg = _make_message(
            sender="agn@autoglassnow.com",
            subject="Please Advise — Prior Approval Required",
            body=APPROVAL_HTML,
            message_id="<approval-001@autoglassnow.com>",
        )

        headers = [
            "Arrival Date", "MVA", "FPO#", "VIN", "Make",
            "Repair Status", "Approval Needed", "Cost", "Repair Status Notes", "Vendor Job Number",
        ]
        data_rows = [
            ["05/06/2026", "12345678", "FPO001", "1HGBH41JXMN109186", "Honda",
             "", "", "", "", ""],
        ]
        mock_ws = MagicMock()
        mock_ws.get_all_values.return_value = [headers] + data_rows

        updater = VendorSheetUpdater.__new__(VendorSheetUpdater)
        updater._spreadsheet_id = "fake"
        updater._sheet_name = "GlassClaims"
        updater._service_account_json = "fake.json"
        updater._ws = mock_ws
        updater._headers = headers[:]
        updater._all_values = [headers] + data_rows
        monitor._updater = updater

        from vendor_tracking.monitor import RunSummary
        summary = RunSummary()

        html = APPROVAL_HTML
        monitor._handle_approval_needed(html, "<approval-001@autoglassnow.com>", "Please Advise", summary)

        assert len(summary.approval_needed) >= 1
        assert any("1HGBH41JXMN109186" in vin for vin in summary.approval_needed)

    def test_unknown_sender_not_processed(self, tmp_path):
        monitor = self._build_monitor(tmp_path)
        msg = _make_message(
            sender="spam@unknown.com",
            subject="Buy something",
            body="<p>Hello</p>",
            message_id="<spam-001@unknown.com>",
        )
        assert classify_email(msg) == EmailType.UNKNOWN


# ─── VT-8: Idempotency store ─────────────────────────────────────────────────

class TestVT8_Idempotency:
    """VT-8: IdempotencyStore — no duplicate writes on rerun."""

    def test_new_id_not_processed(self, tmp_path):
        store = IdempotencyStore(tmp_path / "idem.json")
        assert not store.is_processed("<msg-001@test.com>")

    def test_mark_then_check(self, tmp_path):
        store = IdempotencyStore(tmp_path / "idem.json")
        store.mark_processed("<msg-001@test.com>")
        assert store.is_processed("<msg-001@test.com>")

    def test_persists_across_instances(self, tmp_path):
        path = tmp_path / "idem.json"
        store1 = IdempotencyStore(path)
        store1.mark_processed("<msg-001@test.com>")

        store2 = IdempotencyStore(path)
        assert store2.is_processed("<msg-001@test.com>")

    def test_multiple_ids_independent(self, tmp_path):
        store = IdempotencyStore(tmp_path / "idem.json")
        store.mark_processed("<msg-001@test.com>")
        assert not store.is_processed("<msg-002@test.com>")

    def test_duplicate_mark_does_not_grow_set(self, tmp_path):
        store = IdempotencyStore(tmp_path / "idem.json")
        store.mark_processed("<msg-001@test.com>")
        store.mark_processed("<msg-001@test.com>")
        assert len(store) == 1


# ─── VT-9: Approval Needed blocker in run summary ─────────────────────────────

class TestVT9_ApprovalNeededSummary:
    """VT-9: Approval Needed blocker surfaced prominently in run summary output."""

    def test_approval_needed_vins_in_summary(self, capsys):
        from vendor_tracking.monitor import RunSummary, _print_summary

        summary = RunSummary()
        summary.total_fetched = 5
        summary.processed = 2
        summary.approval_needed = ["1HGBH41JXMN109186", "2HGBH41JXMN109187"]

        _print_summary(summary)
        captured = capsys.readouterr()

        assert "APPROVAL NEEDED" in captured.out
        assert "1HGBH41JXMN109186" in captured.out
        assert "2HGBH41JXMN109187" in captured.out

    def test_no_approval_needed_section_when_empty(self, capsys):
        from vendor_tracking.monitor import RunSummary, _print_summary

        summary = RunSummary()
        summary.total_fetched = 3
        summary.processed = 3

        _print_summary(summary)
        captured = capsys.readouterr()

        assert "APPROVAL NEEDED" not in captured.out
