"""
Unit Tests — close_workitem.py
==============================

Tests for target-building and summary logging. No live browser required.

E2E smoke test (opt-in):
    set GLASS_RUN_E2E_TESTS=1
    set GLASS_E2E_MVA_OPEN_GLASS=<mva with open glass work item>
    .venv\\Scripts\\python.exe -m pytest tests/test_close_workitem.py -v -m e2e
"""

import argparse
import csv
import os
import tempfile

import pytest

import close_workitem as cw


# ─── Unit tests ──────────────────────────────────────────────────────────────

class TestBuildTargets:
    def _args(self, mva=None, csv_path=None):
        ns = argparse.Namespace()
        ns.mva = mva
        ns.csv_path = csv_path
        return ns

    def test_single_mva(self):
        targets = cw._build_targets(self._args(mva="12345678"))
        assert targets == ["12345678"]

    def test_single_mva_strips_whitespace(self):
        targets = cw._build_targets(self._args(mva="  99887766  "))
        assert targets == ["99887766"]

    def test_csv_produces_mva_list(self, tmp_path):
        csv_file = tmp_path / "mvas.csv"
        csv_file.write_text("mva\n11111111\n22222222\n33333333\n")
        targets = cw._build_targets(self._args(csv_path=str(csv_file)))
        assert targets == ["11111111", "22222222", "33333333"]

    def test_csv_skips_blank_mva_rows(self, tmp_path):
        csv_file = tmp_path / "mvas.csv"
        csv_file.write_text("mva\n11111111\n\n22222222\n")
        targets = cw._build_targets(self._args(csv_path=str(csv_file)))
        assert targets == ["11111111", "22222222"]


class TestLogSummary:
    def _result(self, mva, result, detail=""):
        return {"mva": mva, "result": result, "detail": detail}

    def test_all_closed_returns_zero_counts(self):
        results = [
            self._result("11111111", cw.RESULT_CLOSED),
            self._result("22222222", cw.RESULT_CLOSED),
        ]
        not_found, failed = cw._log_summary(results)
        assert not_found == 0
        assert failed == 0

    def test_not_found_counted(self):
        results = [
            self._result("11111111", cw.RESULT_CLOSED),
            self._result("22222222", cw.RESULT_NOT_FOUND),
        ]
        not_found, failed = cw._log_summary(results)
        assert not_found == 1
        assert failed == 0

    def test_nav_failed_counted_as_failure(self):
        results = [self._result("11111111", cw.RESULT_NAV_FAILED)]
        not_found, failed = cw._log_summary(results)
        assert not_found == 0
        assert failed == 1

    def test_error_counted_as_failure(self):
        results = [self._result("11111111", cw.RESULT_ERROR)]
        _, failed = cw._log_summary(results)
        assert failed == 1

    def test_timeout_counted_in_both(self):
        results = [self._result("11111111", cw.RESULT_TIMEOUT)]
        not_found, failed = cw._log_summary(results)
        assert not_found == 0
        assert failed == 1

    def test_mixed_results(self):
        results = [
            self._result("11111111", cw.RESULT_CLOSED),
            self._result("22222222", cw.RESULT_NOT_FOUND),
            self._result("33333333", cw.RESULT_ERROR),
            self._result("44444444", cw.RESULT_NAV_FAILED),
        ]
        not_found, failed = cw._log_summary(results)
        assert not_found == 1
        assert failed == 2


class TestBuildTargetsValidation:
    def _args(self, csv_path):
        ns = argparse.Namespace()
        ns.mva = None
        ns.csv_path = csv_path
        return ns

    def test_missing_file_exits(self, tmp_path):
        """Non-existent CSV path must exit with an error, not raise FileNotFoundError."""
        with pytest.raises(SystemExit):
            cw._build_targets(self._args(str(tmp_path / "missing.csv")))

    def test_csv_without_mva_column_exits(self, tmp_path):
        """CSV missing the 'mva' column must exit with a clear error."""
        f = tmp_path / "bad.csv"
        f.write_text("vehicle,action\n11111111,Replace\n")
        with pytest.raises(SystemExit):
            cw._build_targets(self._args(str(f)))

    def test_empty_csv_exits(self, tmp_path):
        """CSV with header but no data rows must exit rather than silently succeed."""
        f = tmp_path / "empty.csv"
        f.write_text("mva\n")
        with pytest.raises(SystemExit):
            cw._build_targets(self._args(str(f)))


# ─── E2E smoke test (opt-in) ─────────────────────────────────────────────────

_RUN_E2E = os.getenv("GLASS_RUN_E2E_TESTS", "").strip().lower() in {"1", "true", "yes"}

pytestmark_e2e = pytest.mark.e2e


@pytest.mark.e2e
@pytest.mark.skipif(not _RUN_E2E, reason="Set GLASS_RUN_E2E_TESTS=1 to run E2E tests")
def test_smoke_close_single_mva():
    """Close a single known-open glass work item — requires a live Compass session."""
    mva = os.getenv("GLASS_E2E_MVA_OPEN_GLASS", "").strip()
    if not mva:
        pytest.skip("Set GLASS_E2E_MVA_OPEN_GLASS=<mva> to run this test")

    args = argparse.Namespace()
    args.mva = mva
    args.csv_path = None
    args.timeout_seconds = 120
    args.pause = False

    import asyncio

    results = asyncio.run(cw._run_playwright_close_async(args, [mva]))
    assert len(results) == 1
    assert results[0]["result"] == cw.RESULT_CLOSED, (
        f"Expected RESULT_CLOSED, got {results[0]['result']!r}: {results[0].get('detail')}"
    )
