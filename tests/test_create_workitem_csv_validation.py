"""
Unit tests — CSV location validation in create_workitem._build_create_targets().

Valid location values are glass area codes that map to a Compass UI button
(WS/WINDSHIELD/FRONT for windshield, all others for side/back windows).
Lot codes such as BB and APO are not valid and must be rejected before
any browser automation starts.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _make_args(csv_path: str):
    args = MagicMock()
    args.csv = csv_path
    args.mva = None
    args.action = None
    return args


def _write_csv(tmp_path: Path, rows: list[str]) -> str:
    p = tmp_path / "test.csv"
    p.write_text("mva,location,action\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return str(p)


class TestLocationValidation:
    """_build_create_targets rejects rows whose location is not a known glass area code."""

    def test_lot_code_bb_is_rejected(self, tmp_path):
        """BB is a lot location code, not a glass area — must be caught before browser launch."""
        from create_workitem import _build_create_targets

        csv = _write_csv(tmp_path, ["59000001,BB,Replace"])
        with pytest.raises(SystemExit):
            _build_create_targets(_make_args(csv))

    def test_lot_code_apo_is_rejected(self, tmp_path):
        """APO is a request location code, not a glass area."""
        from create_workitem import _build_create_targets

        csv = _write_csv(tmp_path, ["59000001,APO,Replace"])
        with pytest.raises(SystemExit):
            _build_create_targets(_make_args(csv))

    def test_ws_is_accepted(self, tmp_path):
        from create_workitem import _build_create_targets

        csv = _write_csv(tmp_path, ["59000001,WS,Replace"])
        targets = _build_create_targets(_make_args(csv))
        assert len(targets) == 1

    def test_side_window_codes_are_accepted(self, tmp_path):
        """FLD, FRD, RLD, RRD, FLV, FRV, BW, SR, RLQ, RRQ, FRW are valid glass areas."""
        from create_workitem import _build_create_targets

        side_codes = ["FLD", "FRD", "RLD", "RRD", "FLV", "FRV", "BW", "SR", "RLQ", "RRQ", "FRW"]
        rows = [f"5900000{i},{code},Replace" for i, code in enumerate(side_codes)]
        csv = _write_csv(tmp_path, rows)
        targets = _build_create_targets(_make_args(csv))
        assert len(targets) == len(side_codes)

    def test_windshield_alias_accepted(self, tmp_path):
        from create_workitem import _build_create_targets

        csv = _write_csv(tmp_path, ["59000001,WINDSHIELD,Repair"])
        targets = _build_create_targets(_make_args(csv))
        assert len(targets) == 1

    def test_location_check_is_case_insensitive(self, tmp_path):
        from create_workitem import _build_create_targets

        csv = _write_csv(tmp_path, ["59000001,ws,Replace"])
        targets = _build_create_targets(_make_args(csv))
        assert len(targets) == 1

    def test_invalid_location_error_message_names_the_bad_value(self, tmp_path, caplog):
        """The error log must name the invalid location so the user knows what to fix."""
        import logging
        from create_workitem import _build_create_targets

        csv = _write_csv(tmp_path, ["59000001,BB,Replace"])
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit):
                _build_create_targets(_make_args(csv))

        assert "BB" in caplog.text
