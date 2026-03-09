"""
Unit Tests for GlassOrchestrator — Phase-level logic without external dependencies.

UT-1: Suffix Regex Accuracy
UT-2: HTML Extraction
UT-3: Idempotency Check
UT-4: Sanitization
"""

import re
import json
from datetime import datetime

import pytest

from GlassOrchestrator import (
    MVA_PATTERN,
    _load_local_config_overrides,
    _load_runtime_config,
    _extract_body,
    _parse_html_descriptions,
    is_duplicate,
    parse_descriptions_to_manifest,
)


# ─── UT-1: Suffix Regex Accuracy ─────────────────────────────────────────────


class TestUT1_SuffixRegex:
    """Verify the parser correctly extracts the 8-digit MVA and maps
    Damage Type / Claim# for all four suffix variations."""

    def test_plain_mva(self):
        """59340120 → Replacement, Missing"""
        m = MVA_PATTERN.match("59340120")
        assert m is not None
        assert m.group(1) == "59340120"
        assert m.group(2) == ""

    def test_repair_suffix(self):
        """59340120r → Repair, Missing"""
        m = MVA_PATTERN.match("59340120r")
        assert m is not None
        assert m.group(1) == "59340120"
        assert "r" in m.group(2)

    def test_claim_suffix(self):
        """59340120c → Replacement, Listed"""
        m = MVA_PATTERN.match("59340120c")
        assert m is not None
        assert m.group(1) == "59340120"
        assert "c" in m.group(2)

    def test_both_suffixes(self):
        """59340120rc → Repair, Listed"""
        m = MVA_PATTERN.match("59340120rc")
        assert m is not None
        assert m.group(1) == "59340120"
        assert "r" in m.group(2) and "c" in m.group(2)

    def test_phase2_mapping_plain(self):
        """End-to-end: plain MVA → Replacement + Missing"""
        manifest, mva_list = parse_descriptions_to_manifest(
            ["59340120"], datetime(2026, 3, 5)
        )
        assert "59340120" in manifest
        assert manifest["59340120"]["Damage Type"] == "Replacement"
        assert manifest["59340120"]["Claim#"] == "Missing"
        assert mva_list == ["59340120"]

    def test_phase2_mapping_repair(self):
        """59340120r → Repair + Missing"""
        manifest, _ = parse_descriptions_to_manifest(["59340120r"], datetime(2026, 3, 5))
        assert manifest["59340120"]["Damage Type"] == "Repair"
        assert manifest["59340120"]["Claim#"] == "Missing"

    def test_phase2_mapping_claim(self):
        """59340120c → Replacement + Listed"""
        manifest, _ = parse_descriptions_to_manifest(["59340120c"], datetime(2026, 3, 5))
        assert manifest["59340120"]["Damage Type"] == "Replacement"
        assert manifest["59340120"]["Claim#"] == "Listed"

    def test_phase2_mapping_both(self):
        """59340120rc → Repair + Listed"""
        manifest, _ = parse_descriptions_to_manifest(["59340120rc"], datetime(2026, 3, 5))
        assert manifest["59340120"]["Damage Type"] == "Repair"
        assert manifest["59340120"]["Claim#"] == "Listed"

    def test_phase2_all_four_variations(self):
        """Process all four variations in one batch."""
        descriptions = ["59340120", "59340121r", "59340122c", "59340123rc"]
        manifest, mva_list = parse_descriptions_to_manifest(descriptions, datetime(2026, 3, 5))
        assert len(manifest) == 4
        assert len(mva_list) == 4
        assert manifest["59340120"]["Damage Type"] == "Replacement"
        assert manifest["59340120"]["Claim#"] == "Missing"
        assert manifest["59340121"]["Damage Type"] == "Repair"
        assert manifest["59340121"]["Claim#"] == "Missing"
        assert manifest["59340122"]["Damage Type"] == "Replacement"
        assert manifest["59340122"]["Claim#"] == "Listed"
        assert manifest["59340123"]["Damage Type"] == "Repair"
        assert manifest["59340123"]["Claim#"] == "Listed"


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
        "59340120|03/05/2026",
        "59340121|03/05/2026",
        "59340122|03/04/2026",
    }

    def test_duplicate_returns_true(self):
        assert is_duplicate("59340120", "03/05/2026", self.MOCK_EXISTING) is True

    def test_new_mva_returns_false(self):
        assert is_duplicate("99999999", "03/05/2026", self.MOCK_EXISTING) is False

    def test_same_mva_different_date_returns_false(self):
        assert is_duplicate("59340120", "03/06/2026", self.MOCK_EXISTING) is False

    def test_empty_existing_returns_false(self):
        assert is_duplicate("59340120", "03/05/2026", set()) is False


# ─── UT-4: Sanitization ──────────────────────────────────────────────────────


class TestUT4_Sanitization:
    """Ensure malformed entries are rejected and never reach the MVA list."""

    def test_too_short(self):
        manifest, mva_list = parse_descriptions_to_manifest(["12345"], datetime(2026, 3, 5))
        assert manifest == {}
        assert mva_list == []

    def test_no_digits(self):
        manifest, mva_list = parse_descriptions_to_manifest(["abcdefgh"], datetime(2026, 3, 5))
        assert manifest == {}
        assert mva_list == []

    def test_too_long(self):
        manifest, mva_list = parse_descriptions_to_manifest(["123456789"], datetime(2026, 3, 5))
        assert manifest == {}
        assert mva_list == []

    def test_mixed_valid_and_invalid(self):
        descriptions = ["59340120", "12345", "abcdefgh", "59340121r"]
        manifest, mva_list = parse_descriptions_to_manifest(descriptions, datetime(2026, 3, 5))
        assert len(manifest) == 2
        assert set(mva_list) == {"59340120", "59340121"}

    def test_special_characters(self):
        manifest, mva_list = parse_descriptions_to_manifest(["5934012!"], datetime(2026, 3, 5))
        assert manifest == {}
        assert mva_list == []

    def test_whitespace_only(self):
        manifest, mva_list = parse_descriptions_to_manifest(["   "], datetime(2026, 3, 5))
        assert manifest == {}
        assert mva_list == []

    def test_invalid_suffix(self):
        """'x' is not a valid suffix — should be rejected."""
        manifest, mva_list = parse_descriptions_to_manifest(["59340120x"], datetime(2026, 3, 5))
        assert manifest == {}
        assert mva_list == []


# ─── UT-5: Local Config Overrides ───────────────────────────────────────────


class TestUT5_LocalConfigOverrides:
    """Validate local override loading and merge precedence behavior."""

    def test_missing_local_config_returns_empty_dict(self, tmp_path):
        local_path = tmp_path / "orchestrator_config.local.json"
        loaded = _load_local_config_overrides(local_path)
        assert loaded == {}

    def test_invalid_json_local_config_returns_empty_dict(self, tmp_path, caplog):
        local_path = tmp_path / "orchestrator_config.local.json"
        local_path.write_text("{invalid", encoding="utf-8")

        loaded = _load_local_config_overrides(local_path)

        assert loaded == {}
        assert "Local config override load failed" in caplog.text

    def test_non_dict_local_config_returns_empty_dict(self, tmp_path):
        local_path = tmp_path / "orchestrator_config.local.json"
        local_path.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")

        loaded = _load_local_config_overrides(local_path)
        assert loaded == {}

    def test_valid_local_config_returns_dict(self, tmp_path):
        local_path = tmp_path / "orchestrator_config.local.json"
        local_path.write_text(
            json.dumps({"sheet_name": "LocalGlassClaims", "location": "BOS"}),
            encoding="utf-8",
        )

        loaded = _load_local_config_overrides(local_path)
        assert loaded == {"sheet_name": "LocalGlassClaims", "location": "BOS"}

    def test_local_overrides_take_precedence_over_runtime_config(self, tmp_path):
        runtime_path = tmp_path / "orchestrator_config.json"
        local_path = tmp_path / "orchestrator_config.local.json"

        runtime_path.write_text(
            json.dumps(
                {
                    "sheet_name": "BaseSheet",
                    "location": "APO",
                    "cycle_gap_grace_days": 7,
                }
            ),
            encoding="utf-8",
        )
        local_path.write_text(
            json.dumps({"sheet_name": "LocalSheet", "location": "BOS"}),
            encoding="utf-8",
        )

        merged = _load_runtime_config(runtime_path)
        merged.update(_load_local_config_overrides(local_path))

        assert merged["sheet_name"] == "LocalSheet"
        assert merged["location"] == "BOS"
        # Value present only in runtime config should be preserved.
        assert merged["cycle_gap_grace_days"] == 7
