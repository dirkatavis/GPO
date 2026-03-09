"""
Integration Tests for GlassOrchestrator — System handshakes between components.

IT-1: Gmail Connection & Search  (requires live credentials — skipped by default)
IT-2: Worker Handoff (File Bridge)
IT-3: Merge Reconciliation
IT-4: Spreadsheet Persistence
"""

import csv
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pandas as pd
import pytest

from GlassOrchestrator import (
    COLUMNS,
    CSV_PATH,
    DATA_DIR,
    IMAP_SERVER,
    SPREADSHEET_ID,
    SHEET_NAME,
    TARGET_SENDER,
    _get_worksheet,
    parse_descriptions_to_manifest,
    merge_manifest_with_results,
    persist_new_rows,
)


# ─── IT-1: Gmail Connection & Search ─────────────────────────────────────────


@pytest.mark.skipif(
    not os.getenv("GLASS_EMAIL_ACCOUNT") or not os.getenv("GLASS_EMAIL_PASSWORD"),
    reason="Gmail credentials not configured (set GLASS_EMAIL_ACCOUNT / GLASS_EMAIL_PASSWORD)",
)
class TestIT1_GmailConnection:
    """Verify IMAP authentication and UNSEEN message search."""

    def test_imap_auth_and_search(self):
        import imaplib

        account = os.getenv("GLASS_EMAIL_ACCOUNT")
        password = os.getenv("GLASS_EMAIL_PASSWORD")

        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        try:
            mail.login(account, password)
            mail.select("inbox")
            status, msg_ids = mail.search(None, f'(FROM "{TARGET_SENDER}")')
            assert status == "OK"
            # msg_ids[0] may be empty (no messages) — that's still OK
            count = len(msg_ids[0].split()) if msg_ids[0] else 0
            assert isinstance(count, int)
        finally:
            mail.logout()


# ─── IT-2: Worker Handoff (File Bridge) ──────────────────────────────────────


class TestIT2_WorkerHandoff:
    """Verify CSV formatting and subprocess launch capability."""

    def test_csv_written_correctly(self, tmp_path):
        """Write MVAs to a CSV and validate structure."""
        csv_path = tmp_path / "GlassDataParser.csv"
        mva_list = ["59340120", "59340121", "59340122"]

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["MVA"])
            for mva in mva_list:
                writer.writerow([mva])

        # Validate
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert "MVA" in reader.fieldnames
            rows = list(reader)
            assert len(rows) == 3
            assert rows[0]["MVA"] == "59340120"
            assert rows[2]["MVA"] == "59340122"

    def test_subprocess_can_launch_python(self):
        """Verify subprocess.check_call can invoke Python successfully."""
        # Run a trivial Python command to prove the subprocess mechanism works
        subprocess.check_call(
            [sys.executable, "-c", "print('worker ok')"],
        )

    def test_subprocess_detects_failure(self):
        """Verify subprocess.CalledProcessError is raised on non-zero exit."""
        with pytest.raises(subprocess.CalledProcessError):
            subprocess.check_call(
                [sys.executable, "-c", "import sys; sys.exit(1)"],
            )


# ─── IT-3: Merge Reconciliation ──────────────────────────────────────────────


class TestIT3_MergeReconciliation:
    """Verify left-join logic: missing MVAs produce VIN='N/A', no rows dropped."""

    def test_left_join_with_missing_mva(self, tmp_path, monkeypatch):
        """One MVA present in results, one missing → VIN=N/A for missing."""
        # Build manifest from parsing step
        descriptions = ["59340120", "59340121"]
        manifest, _ = parse_descriptions_to_manifest(descriptions, datetime(2026, 3, 5))

        # Create a mock GlassResults.txt with only ONE of the two MVAs
        results_file = tmp_path / "GlassResults.txt"
        results_file.write_text("MVA,VIN,Desc\n59340120,1HGCM82633A004352,Windshield\n")

        # Patch the RESULTS_PATH used by merge step
        monkeypatch.setattr("GlassOrchestrator.RESULTS_PATH", results_file)

        df = merge_manifest_with_results(manifest)

        assert len(df) == 2  # Both MVAs must be present (no drop)
        row_120 = df[df["MVA"] == "59340120"].iloc[0]
        row_121 = df[df["MVA"] == "59340121"].iloc[0]

        assert row_120["VIN"] == "1HGCM82633A004352"
        assert row_121["VIN"] == "N/A"  # Missing from scraper → N/A

    def test_all_mvas_missing_from_results(self, tmp_path, monkeypatch):
        """No scraper results at all → all VINs become N/A."""
        descriptions = ["59340120", "59340121"]
        manifest, _ = parse_descriptions_to_manifest(descriptions, datetime(2026, 3, 5))

        results_file = tmp_path / "GlassResults.txt"
        results_file.write_text("MVA,VIN,Desc\n")  # header only

        monkeypatch.setattr("GlassOrchestrator.RESULTS_PATH", results_file)

        df = merge_manifest_with_results(manifest)

        assert len(df) == 2
        assert (df["VIN"] == "N/A").all()

    def test_results_file_missing(self, tmp_path, monkeypatch):
        """No GlassResults.txt file → degrade gracefully, all VINs = N/A."""
        descriptions = ["59340120"]
        manifest, _ = parse_descriptions_to_manifest(descriptions, datetime(2026, 3, 5))

        monkeypatch.setattr("GlassOrchestrator.RESULTS_PATH", tmp_path / "nonexistent.txt")

        df = merge_manifest_with_results(manifest)
        assert len(df) == 1
        assert df.iloc[0]["VIN"] == "N/A"


# ─── IT-4: Spreadsheet Persistence ───────────────────────────────────────────


class TestIT4_SpreadsheetPersistence:
    """Verify data is appended to Google Sheet without overwriting."""

    def _make_test_df(self, mvas, date="03/05/2026"):
        rows = []
        for mva in mvas:
            rows.append({
                "Arrival Date": date,
                "MVA": mva,
                "VIN": "1HGCM82633A004352",
                "Make": "Windshield",
                "Location": "APO",
                "Damage Type": "Replacement",
                "Claim#": "Missing",
                "WorkItem": "verified",
            })
        return pd.DataFrame(rows, columns=COLUMNS)

    def _mock_worksheet(self, existing_rows=None):
        """Create a mock worksheet with optional existing data."""
        ws = MagicMock()
        header = ["Arrival Date", "MVA", "VIN", "Make", "Location",
                  "Damage Type", "Claim#", "WorkItem"]
        if existing_rows is None:
            existing_rows = []
        ws.get_all_values.return_value = [header] + existing_rows
        return ws

    @patch("GlassOrchestrator._get_worksheet")
    def test_creates_new_rows(self, mock_get_ws):
        """First write updates cells in the sheet."""
        ws = self._mock_worksheet()
        mock_get_ws.return_value = ws

        df = self._make_test_df(["59340120", "59340121"])
        new_rows = persist_new_rows(df)

        assert len(new_rows) == 2
        ws.insert_rows.assert_called_once()
        written = ws.insert_rows.call_args[0][0]
        assert len(written) == 2
        assert written[0][1] == "59340120"
        assert written[1][1] == "59340121"

    @patch("GlassOrchestrator._get_worksheet")
    def test_appends_without_overwriting(self, mock_get_ws):
        """Second write appends new rows; existing data untouched."""
        existing = [["03/05/2026", "59340120", "1HGCM82633A004352",
                      "Windshield", "APO", "Replacement", "Missing", "verified"]]
        ws = self._mock_worksheet(existing)
        mock_get_ws.return_value = ws

        df = self._make_test_df(["59340121"])
        new_rows = persist_new_rows(df)

        assert len(new_rows) == 1
        ws.insert_rows.assert_called_once()
        written = ws.insert_rows.call_args[0][0]
        assert written[0][1] == "59340121"

    @patch("GlassOrchestrator._get_worksheet")
    def test_idempotency_prevents_duplicate(self, mock_get_ws):
        """Same MVA+Date already in sheet → no rows inserted."""
        existing = [["03/05/2026", "59340120", "1HGCM82633A004352",
                      "Windshield", "APO", "Replacement", "Missing", "verified"]]
        ws = self._mock_worksheet(existing)
        mock_get_ws.return_value = ws

        df = self._make_test_df(["59340120"])
        new_rows = persist_new_rows(df)

        assert len(new_rows) == 0
        ws.insert_rows.assert_not_called()

    @patch("GlassOrchestrator._get_worksheet")
    def test_correct_columns_written(self, mock_get_ws):
        """Verify all 8 columns match the expected schema."""
        ws = self._mock_worksheet()
        mock_get_ws.return_value = ws

        df = self._make_test_df(["59340120"])
        persist_new_rows(df)

        written = ws.insert_rows.call_args[0][0]
        assert written[0] == ["03/05/2026", "59340120", "1HGCM82633A004352",
                                "Windshield", "APO", "Replacement", "Missing", "verified"]


# ─── IT-5: Spreadsheet Configuration Health ──────────────────────────────────


class TestIT5_SpreadsheetConfigurationHealth:
    """Integration checks for spreadsheet configuration and accessibility."""

    def test_spreadsheet_id_is_not_placeholder(self):
        """Configured spreadsheet id should not be the default placeholder."""
        assert SPREADSHEET_ID != "YOUR_SPREADSHEET_ID_HERE", (
            "SPREADSHEET_ID is still placeholder. Set GLASS_SPREADSHEET_ID "
            "or update orchestrator_config.json."
        )

    def test_service_account_can_open_configured_sheet(self):
        """Service account should open configured sheet/tab successfully."""
        ws = _get_worksheet()
        assert ws is not None
        assert ws.title == SHEET_NAME
