"""
Unit Tests for GlassOrchestrator — Phase-level logic without external dependencies.

UT-1: Suffix Regex Accuracy
UT-2: HTML Extraction
UT-3: Idempotency Check
UT-4: Sanitization
"""

import re
from datetime import datetime

import pytest

from GlassOrchestrator import (
    MVA_PATTERN,
    _extract_body,
    _parse_html_descriptions,
    is_duplicate,
    phase2_parse,
)


# ─── UT-1: Suffix Regex Accuracy ─────────────────────────────────────────────


class TestUT1_SuffixRegex:
    """Verify the parser correctly extracts the 8-digit MVA and maps
    Damage Type / Claim# for all four suffix variations."""

    def test_plain_mva(self):
        """59340120 → Replacement, Pending"""
        m = MVA_PATTERN.match("59340120")
        assert m is not None
        assert m.group(1) == "59340120"
        assert m.group(2) == ""

    def test_repair_suffix(self):
        """59340120r → Repair, Pending"""
        m = MVA_PATTERN.match("59340120r")
        assert m is not None
        assert m.group(1) == "59340120"
        assert "r" in m.group(2)

    def test_claim_suffix(self):
        """59340120c → Replacement, Claim Generated"""
        m = MVA_PATTERN.match("59340120c")
        assert m is not None
        assert m.group(1) == "59340120"
        assert "c" in m.group(2)

    def test_both_suffixes(self):
        """59340120rc → Repair, Claim Generated"""
        m = MVA_PATTERN.match("59340120rc")
        assert m is not None
        assert m.group(1) == "59340120"
        assert "r" in m.group(2) and "c" in m.group(2)

    def test_phase2_mapping_plain(self):
        """End-to-end: plain MVA → Replacement + Pending"""
        manifest, mva_list = phase2_parse(
            ["59340120"], datetime(2026, 3, 5)
        )
        assert "59340120" in manifest
        assert manifest["59340120"]["Damage Type"] == "Replacement"
        assert manifest["59340120"]["Claim#"] == "Pending"
        assert mva_list == ["59340120"]

    def test_phase2_mapping_repair(self):
        """59340120r → Repair + Pending"""
        manifest, _ = phase2_parse(["59340120r"], datetime(2026, 3, 5))
        assert manifest["59340120"]["Damage Type"] == "Repair"
        assert manifest["59340120"]["Claim#"] == "Pending"

    def test_phase2_mapping_claim(self):
        """59340120c → Replacement + Claim Generated"""
        manifest, _ = phase2_parse(["59340120c"], datetime(2026, 3, 5))
        assert manifest["59340120"]["Damage Type"] == "Replacement"
        assert manifest["59340120"]["Claim#"] == "Claim Generated"

    def test_phase2_mapping_both(self):
        """59340120rc → Repair + Claim Generated"""
        manifest, _ = phase2_parse(["59340120rc"], datetime(2026, 3, 5))
        assert manifest["59340120"]["Damage Type"] == "Repair"
        assert manifest["59340120"]["Claim#"] == "Claim Generated"

    def test_phase2_all_four_variations(self):
        """Process all four variations in one batch."""
        descriptions = ["59340120", "59340121r", "59340122c", "59340123rc"]
        manifest, mva_list = phase2_parse(descriptions, datetime(2026, 3, 5))
        assert len(manifest) == 4
        assert len(mva_list) == 4
        assert manifest["59340120"]["Damage Type"] == "Replacement"
        assert manifest["59340120"]["Claim#"] == "Pending"
        assert manifest["59340121"]["Damage Type"] == "Repair"
        assert manifest["59340121"]["Claim#"] == "Pending"
        assert manifest["59340122"]["Damage Type"] == "Replacement"
        assert manifest["59340122"]["Claim#"] == "Claim Generated"
        assert manifest["59340123"]["Damage Type"] == "Repair"
        assert manifest["59340123"]["Claim#"] == "Claim Generated"


# ─── UT-2: HTML Extraction ────────────────────────────────────────────────────


class TestUT2_HTMLExtraction:
    """Verify that Description column values are correctly extracted
    from a mock HTML table representing an Orca Scan email body."""

    MOCK_HTML = """
    <html><body>
    <table>
      <tr><th>Date</th><th>MVA</th><th>Description</th><th>Other</th></tr>
      <tr><td>2026-03-05</td><td>001</td><td>59340120</td><td>X</td></tr>
      <tr><td>2026-03-05</td><td>002</td><td>59340121r</td><td>Y</td></tr>
      <tr><td>2026-03-05</td><td>003</td><td>59340122rc</td><td>Z</td></tr>
    </table>
    </body></html>
    """

    # Orca Scan packs multiple MVAs into a single Description cell with newlines
    ORCA_HTML = """
    <html><body>
    <table id="rowData" cellspacing="0" cellpadding="4" border="1">
      <thead>
        <tr>
          <th>Type</th><th>Name</th><th>Description</th>
          <th>Quantity</th><th>Storage Area</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>0205</td><td></td><td>59340120c
58157002
58135663cr
57193500r</td>
          <td>1</td><td></td>
        </tr>
      </tbody>
    </table>
    </body></html>
    """

    def test_extracts_description_column(self):
        result = _parse_html_descriptions(self.MOCK_HTML)
        assert result == ["59340120", "59340121r", "59340122rc"]

    def test_orca_multiline_cell_splits_into_individual_mvas(self):
        result = _parse_html_descriptions(self.ORCA_HTML)
        assert result == ["59340120c", "58157002", "58135663cr", "57193500r"]

    def test_returns_empty_on_no_table(self):
        result = _parse_html_descriptions("<html><body><p>No table</p></body></html>")
        assert result == []

    def test_returns_empty_on_no_description_header(self):
        html = """
        <table>
          <tr><th>Date</th><th>MVA</th><th>Notes</th></tr>
          <tr><td>2026-03-05</td><td>001</td><td>foo</td></tr>
        </table>
        """
        result = _parse_html_descriptions(html)
        assert result == []

    def test_skips_empty_description_cells(self):
        html = """
        <table>
          <tr><th>Description</th></tr>
          <tr><td>59340120</td></tr>
          <tr><td></td></tr>
          <tr><td>59340121r</td></tr>
        </table>
        """
        result = _parse_html_descriptions(html)
        assert result == ["59340120", "59340121r"]

    def test_extract_body_prefers_html_with_table(self):
        """_extract_body should return HTML when it contains a <table>."""
        import email as email_mod
        msg = email_mod.mime.multipart.MIMEMultipart("mixed")
        from email.mime.text import MIMEText
        msg.attach(MIMEText("<table><tr><th>Description</th></tr></table>", "html"))
        msg.attach(MIMEText("plain text fallback", "plain"))
        body = _extract_body(msg)
        assert "<table>" in body


# ─── UT-3: Idempotency Check ─────────────────────────────────────────────────


class TestUT3_Idempotency:
    """Verify the duplicate-detection logic using MVA+Date composite keys."""

    MOCK_EXISTING = {
        "59340120|2026-03-05",
        "59340121|2026-03-05",
        "59340122|2026-03-04",
    }

    def test_duplicate_returns_true(self):
        assert is_duplicate("59340120", "2026-03-05", self.MOCK_EXISTING) is True

    def test_new_mva_returns_false(self):
        assert is_duplicate("99999999", "2026-03-05", self.MOCK_EXISTING) is False

    def test_same_mva_different_date_returns_false(self):
        assert is_duplicate("59340120", "2026-03-06", self.MOCK_EXISTING) is False

    def test_empty_existing_returns_false(self):
        assert is_duplicate("59340120", "2026-03-05", set()) is False


# ─── UT-4: Sanitization ──────────────────────────────────────────────────────


class TestUT4_Sanitization:
    """Ensure malformed entries are rejected and never reach the MVA list."""

    def test_too_short(self):
        manifest, mva_list = phase2_parse(["12345"], datetime(2026, 3, 5))
        assert manifest == {}
        assert mva_list == []

    def test_no_digits(self):
        manifest, mva_list = phase2_parse(["abcdefgh"], datetime(2026, 3, 5))
        assert manifest == {}
        assert mva_list == []

    def test_too_long(self):
        manifest, mva_list = phase2_parse(["123456789"], datetime(2026, 3, 5))
        assert manifest == {}
        assert mva_list == []

    def test_mixed_valid_and_invalid(self):
        descriptions = ["59340120", "12345", "abcdefgh", "59340121r"]
        manifest, mva_list = phase2_parse(descriptions, datetime(2026, 3, 5))
        assert len(manifest) == 2
        assert set(mva_list) == {"59340120", "59340121"}

    def test_special_characters(self):
        manifest, mva_list = phase2_parse(["5934012!"], datetime(2026, 3, 5))
        assert manifest == {}
        assert mva_list == []

    def test_whitespace_only(self):
        manifest, mva_list = phase2_parse(["   "], datetime(2026, 3, 5))
        assert manifest == {}
        assert mva_list == []

    def test_invalid_suffix(self):
        """'x' is not a valid suffix — should be rejected."""
        manifest, mva_list = phase2_parse(["59340120x"], datetime(2026, 3, 5))
        assert manifest == {}
        assert mva_list == []
