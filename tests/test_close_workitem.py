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
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

import close_workitem as cw


# ─── Unit tests ──────────────────────────────────────────────────────────────

class TestBuildTargets:
    def _args(self, mva=None, csv_path=None, complaint_type=None):
        ns = argparse.Namespace()
        ns.mva = mva
        ns.csv_path = csv_path
        ns.complaint_type = complaint_type
        return ns

    def test_single_mva(self):
        targets = cw._build_targets(self._args(mva="12345678"))
        assert targets == [{"mva": "12345678", "complaint_type": "Glass"}]

    def test_single_mva_strips_whitespace(self):
        targets = cw._build_targets(self._args(mva="  99887766  "))
        assert targets == [{"mva": "99887766", "complaint_type": "Glass"}]

    def test_single_mva_with_explicit_type(self):
        targets = cw._build_targets(self._args(mva="12345678", complaint_type="PM"))
        assert targets == [{"mva": "12345678", "complaint_type": "PM"}]

    def test_csv_produces_mva_list(self, tmp_path):
        csv_file = tmp_path / "mvas.csv"
        csv_file.write_text("mva,Type\n11111111,Glass\n22222222,PM\n33333333,Glass\n")
        targets = cw._build_targets(self._args(csv_path=str(csv_file)))
        assert targets == [
            {"mva": "11111111", "complaint_type": "Glass"},
            {"mva": "22222222", "complaint_type": "PM"},
            {"mva": "33333333", "complaint_type": "Glass"},
        ]

    def test_csv_skips_blank_mva_rows(self, tmp_path):
        csv_file = tmp_path / "mvas.csv"
        csv_file.write_text("mva,Type\n11111111,Glass\n\n22222222,Glass\n")
        targets = cw._build_targets(self._args(csv_path=str(csv_file)))
        assert targets == [
            {"mva": "11111111", "complaint_type": "Glass"},
            {"mva": "22222222", "complaint_type": "Glass"},
        ]


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


def _make_async_playwright_mocks():
    page = AsyncMock()
    page.url = "https://avisbudget.palantirfoundry.com/workspace/fleet-operations-pwa/health"

    context = AsyncMock()
    context.close = AsyncMock()

    pw = MagicMock()
    pw.chromium.launch_persistent_context = AsyncMock(return_value=context)

    async_pw_cm = AsyncMock()
    async_pw_cm.__aenter__ = AsyncMock(return_value=pw)
    async_pw_cm.__aexit__ = AsyncMock(return_value=None)

    return pw, async_pw_cm, context, page


class TestRunPlaywrightCloseAsync:
    def _args(self, timeout_seconds=90):
        return argparse.Namespace(timeout_seconds=timeout_seconds)

    def _patch_defaults(self, monkeypatch, async_pw_cm, context, page):
        monkeypatch.setattr("close_workitem.async_playwright", lambda: async_pw_cm)
        monkeypatch.setattr("close_workitem._is_edge_running", lambda: False)
        monkeypatch.setattr("close_workitem.resolve_headless", lambda: False)
        monkeypatch.setattr("close_workitem.resolve_edge_user_data_dir", lambda: r"C:\\Users\\test\\AppData\\Local\\Microsoft\\Edge\\User Data")
        monkeypatch.setattr("close_workitem.resolve_edge_profile_directory", lambda: "Default")
        monkeypatch.setattr("close_workitem.resolve_initial_delay", lambda: 0)
        monkeypatch.setattr("close_workitem.resolve_step_delay", lambda: 0)
        monkeypatch.setattr(
            "close_workitem.ensure_profile_context",
            AsyncMock(return_value=(context, page)),
        )
        monkeypatch.setattr("close_workitem.pw_warmup_compass", AsyncMock())
        monkeypatch.setattr("close_workitem.pw_navigate_to_mva", AsyncMock())
        monkeypatch.setattr(
            "close_workitem._playwright_close_work_item",
            AsyncMock(return_value=(cw.RESULT_NOT_FOUND, "")),
        )
        monkeypatch.setattr("close_workitem._capture_playwright_screenshot", AsyncMock())

    def test_logs_runtime_config_on_startup(self, monkeypatch, caplog):
        pw, async_pw_cm, context, page = _make_async_playwright_mocks()
        self._patch_defaults(monkeypatch, async_pw_cm, context, page)

        caplog.set_level("INFO")
        results = asyncio.run(cw._run_playwright_close_async(self._args(), []))

        assert results == []
        assert "[CLOSE] Runtime config | login_url=" in caplog.text
        assert "profile=Default" in caplog.text
        pw.chromium.launch_persistent_context.assert_called_once()

    def test_logs_navigation_target_and_landing_url(self, monkeypatch, caplog):
        _, async_pw_cm, context, page = _make_async_playwright_mocks()
        self._patch_defaults(monkeypatch, async_pw_cm, context, page)

        async def _navigate_side_effect(target_page, mva):
            target_page.url = f"https://avisbudget.palantirfoundry.com/workspace/fleet-operations-pwa/vehicle/{mva}"

        monkeypatch.setattr("close_workitem.pw_navigate_to_mva", AsyncMock(side_effect=_navigate_side_effect))

        caplog.set_level("INFO")
        asyncio.run(cw._run_playwright_close_async(self._args(), [{"mva": "12345678", "complaint_type": "Glass"}]))

        assert "[CLOSE] 12345678 - navigating to MVA" in caplog.text
        assert "[CLOSE] 12345678 - navigation landed at URL:" in caplog.text

    def test_navigation_timeout_maps_to_timeout_result(self, monkeypatch):
        _, async_pw_cm, context, page = _make_async_playwright_mocks()
        self._patch_defaults(monkeypatch, async_pw_cm, context, page)

        monkeypatch.setattr("close_workitem.pw_navigate_to_mva", AsyncMock(side_effect=asyncio.TimeoutError()))

        results = asyncio.run(cw._run_playwright_close_async(self._args(), [{"mva": "12345678", "complaint_type": "Glass"}]))

        assert results == [{"mva": "12345678", "result": cw.RESULT_TIMEOUT, "detail": ""}]

    def test_navigation_exception_maps_to_nav_failed(self, monkeypatch):
        _, async_pw_cm, context, page = _make_async_playwright_mocks()
        self._patch_defaults(monkeypatch, async_pw_cm, context, page)

        monkeypatch.setattr("close_workitem.pw_navigate_to_mva", AsyncMock(side_effect=RuntimeError("bad route")))

        results = asyncio.run(cw._run_playwright_close_async(self._args(), [{"mva": "12345678", "complaint_type": "Glass"}]))

        assert results == [{"mva": "12345678", "result": cw.RESULT_NAV_FAILED, "detail": ""}]

    def test_ensure_profile_context_runs_before_warmup_and_navigation(self, monkeypatch):
        _, async_pw_cm, context, page = _make_async_playwright_mocks()
        self._patch_defaults(monkeypatch, async_pw_cm, context, page)

        call_order: list[str] = []

        async def _ensure(_context):
            call_order.append("ensure")
            return _context, page

        async def _warmup(_page):
            call_order.append("warmup")

        async def _navigate(_page, _mva):
            call_order.append("navigate")
            _page.url = "https://avisbudget.palantirfoundry.com/workspace/fleet-operations-pwa/vehicle/12345678"

        monkeypatch.setattr("close_workitem.ensure_profile_context", AsyncMock(side_effect=_ensure))
        monkeypatch.setattr("close_workitem.pw_warmup_compass", AsyncMock(side_effect=_warmup))
        monkeypatch.setattr("close_workitem.pw_navigate_to_mva", AsyncMock(side_effect=_navigate))

        asyncio.run(cw._run_playwright_close_async(self._args(), [{"mva": "12345678", "complaint_type": "Glass"}]))

        assert call_order[:3] == ["ensure", "warmup", "navigate"]


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
    args.complaint_type = "Glass"
    args.timeout_seconds = 120
    args.pause = False

    import asyncio

    results = asyncio.run(cw._run_playwright_close_async(args, [{"mva": mva, "complaint_type": "Glass"}]))
    assert len(results) == 1
    assert results[0]["result"] == cw.RESULT_CLOSED, (
        f"Expected RESULT_CLOSED, got {results[0]['result']!r}: {results[0].get('detail')}"
    )
