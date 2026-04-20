"""
Unit Tests for GlassOrchestrator — Phase-level logic without external dependencies.

UT-1: Suffix Regex Accuracy
UT-2: HTML Extraction
UT-3: Idempotency Check
UT-4: Sanitization
UT-7: Location Extraction from Type Column
"""

import re
import json
from datetime import datetime

import pandas as pd
import pytest

from GlassOrchestrator import (
    MVA_PATTERN,
    _load_local_config_overrides,
    _load_runtime_config,
    _extract_body,
    _extract_location_from_type,
    _parse_html_descriptions,
    notify_order_items,
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
            [("0305APO", "59340120")], datetime(2026, 3, 5)
        )
        assert "59340120" in manifest
        assert manifest["59340120"]["Damage Type"] == "Replacement"
        assert manifest["59340120"]["Claim#"] == "Missing"
        assert manifest["59340120"]["Location"] == "APO"
        assert mva_list == ["59340120"]

    def test_phase2_mapping_repair(self):
        """59340120r → Repair + Missing"""
        manifest, _ = parse_descriptions_to_manifest([("0305APO", "59340120r")], datetime(2026, 3, 5))
        assert manifest["59340120"]["Damage Type"] == "Repair"
        assert manifest["59340120"]["Claim#"] == "Missing"

    def test_phase2_mapping_claim(self):
        """59340120c → Replacement + Listed"""
        manifest, _ = parse_descriptions_to_manifest([("0305APO", "59340120c")], datetime(2026, 3, 5))
        assert manifest["59340120"]["Damage Type"] == "Replacement"
        assert manifest["59340120"]["Claim#"] == "Listed"

    def test_phase2_mapping_both(self):
        """59340120rc → Repair + Listed"""
        manifest, _ = parse_descriptions_to_manifest([("0305APO", "59340120rc")], datetime(2026, 3, 5))
        assert manifest["59340120"]["Damage Type"] == "Repair"
        assert manifest["59340120"]["Claim#"] == "Listed"

    def test_phase2_all_four_variations(self):
        """Process all four variations in one batch."""
        descriptions = [("0305APO", "59340120"), ("0305APO", "59340121r"), ("0305APO", "59340122c"), ("0305APO", "59340123rc")]
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
      <tr><th>Type</th><th>Date</th><th>MVA</th><th>Description</th><th>Other</th></tr>
      <tr><td>batch1</td><td>2026-03-05</td><td>001</td><td>59340120</td><td>X</td></tr>
      <tr><td>batch1</td><td>2026-03-05</td><td>002</td><td>59340121r</td><td>Y</td></tr>
      <tr><td>batch1</td><td>2026-03-05</td><td>003</td><td>59340122rc</td><td>Z</td></tr>
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
        assert result == [("batch1", "59340120"), ("batch1", "59340121r"), ("batch1", "59340122rc")]

    def test_orca_multiline_cell_splits_into_individual_mvas(self):
        result = _parse_html_descriptions(self.ORCA_HTML)
        assert result == [("0205", "59340120c"), ("0205", "58157002"), ("0205", "58135663cr"), ("0205", "57193500r")]

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
          <tr><th>Type</th><th>Description</th></tr>
          <tr><td>batch1</td><td>59340120</td></tr>
          <tr><td>batch1</td><td></td></tr>
          <tr><td>batch1</td><td>59340121r</td></tr>
        </table>
        """
        result = _parse_html_descriptions(html)
        assert result == [("batch1", "59340120"), ("batch1", "59340121r")]

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
        manifest, mva_list = parse_descriptions_to_manifest([("0305APO", "12345")], datetime(2026, 3, 5))
        assert manifest == {}
        assert mva_list == []

    def test_no_digits(self):
        manifest, mva_list = parse_descriptions_to_manifest([("0305APO", "abcdefgh")], datetime(2026, 3, 5))
        assert manifest == {}
        assert mva_list == []

    def test_too_long(self):
        manifest, mva_list = parse_descriptions_to_manifest([("0305APO", "123456789")], datetime(2026, 3, 5))
        assert manifest == {}
        assert mva_list == []

    def test_mixed_valid_and_invalid(self):
        descriptions = [("0305APO", "59340120"), ("0305APO", "12345"), ("0305APO", "abcdefgh"), ("0305APO", "59340121r")]
        manifest, mva_list = parse_descriptions_to_manifest(descriptions, datetime(2026, 3, 5))
        assert len(manifest) == 2
        assert set(mva_list) == {"59340120", "59340121"}

    def test_special_characters(self):
        manifest, mva_list = parse_descriptions_to_manifest([("0305APO", "5934012!")], datetime(2026, 3, 5))
        assert manifest == {}
        assert mva_list == []

    def test_whitespace_only(self):
        manifest, mva_list = parse_descriptions_to_manifest([("0305APO", "   ")], datetime(2026, 3, 5))
        assert manifest == {}
        assert mva_list == []

    def test_invalid_suffix(self):
        """'x' is not a valid suffix — should be rejected."""
        manifest, mva_list = parse_descriptions_to_manifest([("0305APO", "59340120x")], datetime(2026, 3, 5))
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

    def test_legacy_local_then_shared_local_override_order(self, tmp_path):
        runtime_path = tmp_path / "orchestrator_config.json"
        shared_local_path = tmp_path / "config.local.json"
        legacy_local_path = tmp_path / "orchestrator_config.local.json"

        runtime_path.write_text(
            json.dumps({"location": "APO", "email_account": "base@company.com"}),
            encoding="utf-8",
        )
        shared_local_path.write_text(
            json.dumps({"email_account": "shared@company.com", "sheet_name": "SharedSheet"}),
            encoding="utf-8",
        )
        legacy_local_path.write_text(
            json.dumps({"email_account": "legacy@company.com"}),
            encoding="utf-8",
        )

        merged = _load_runtime_config(runtime_path)
        merged.update(_load_local_config_overrides(legacy_local_path))
        merged.update(_load_local_config_overrides(shared_local_path))

        # Shared local file can provide orchestrator values.
        assert merged["sheet_name"] == "SharedSheet"
        # Shared local file wins when both define the same key.
        assert merged["email_account"] == "shared@company.com"


# ─── UT-6: Notification Payload ─────────────────────────────────────────────


class TestUT6_NotificationPayload:
    """Ensure notification email includes all persisted rows."""

    def test_notify_includes_replacement_and_repair_rows(self, monkeypatch):
        df = pd.DataFrame(
            [
                {
                    "Arrival Date": "03/09/2026",
                    "MVA": "59654641",
                    "VIN": "1HGCY1F44SA083453",
                    "Make": "HONDA ACCORD",
                    "Location": "APO",
                    "Damage Type": "Replacement",
                    "Claim#": "Listed",
                    "WorkItem": "verified",
                },
                {
                    "Arrival Date": "03/09/2026",
                    "MVA": "60853262",
                    "VIN": "JN8BT3DDXTW297427",
                    "Make": "NISSAN ROGUE AWD",
                    "Location": "APO",
                    "Damage Type": "Repair",
                    "Claim#": "Missing",
                    "WorkItem": "verified",
                },
            ]
        )

        sent_messages = []

        def fake_send(message):
            sent_messages.append(message)

        monkeypatch.setattr("GlassOrchestrator._send_email", fake_send)

        notify_order_items(df)

        assert len(sent_messages) == 1
        assert "(2 items)" in sent_messages[0].subject
        assert "59654641" in sent_messages[0].html_body
        assert "60853262" in sent_messages[0].html_body


# ─── UT-7: Location Extraction from Type Column ─────────────────────────────


class TestUT7_LocationExtraction:
    """Verify location suffix extraction from Type column (e.g., '0420APO' → 'APO')."""

    def test_apo_suffix(self):
        """Type column '0420APO' → Location 'APO'."""
        assert _extract_location_from_type("0420APO") == "APO"

    def test_bb_suffix(self):
        """Type column '0420BB' → Location 'BB'."""
        assert _extract_location_from_type("0420BB") == "BB"

    def test_lowercase_suffix_normalized(self):
        """Type column '0420apo' → Location 'APO' (case-insensitive)."""
        assert _extract_location_from_type("0420apo") == "APO"

    def test_mixed_case_bb(self):
        """Type column '0420Bb' → Location 'BB'."""
        assert _extract_location_from_type("0420Bb") == "BB"

    def test_no_suffix_uses_default(self):
        """Type column '0420' (no suffix) → falls back to default location."""
        result = _extract_location_from_type("0420")
        # Should return the config default location
        assert result == "APO"

    def test_empty_string_uses_default(self):
        """Empty Type column → falls back to default location."""
        result = _extract_location_from_type("")
        assert result == "APO"

    def test_none_value_uses_default(self):
        """None Type column → falls back to default location."""
        result = _extract_location_from_type(None)
        assert result == "APO"

    def test_whitespace_trimmed(self):
        """Type column ' 0420APO ' → Location 'APO' (whitespace trimmed)."""
        assert _extract_location_from_type(" 0420APO ") == "APO"

    def test_unknown_suffix_uses_default(self):
        """Type column '0420XYZ' (unknown suffix) → falls back to default."""
        result = _extract_location_from_type("0420XYZ")
        assert result == "APO"

    def test_manifest_uses_extracted_location(self):
        """parse_descriptions_to_manifest correctly extracts location from Type."""
        manifest, _ = parse_descriptions_to_manifest(
            [("0305BB", "59340120")], datetime(2026, 3, 5)
        )
        assert manifest["59340120"]["Location"] == "BB"
