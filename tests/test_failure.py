"""
Failure & Recovery Tests for GlassOrchestrator — Edge cases.

FT-1: Worker Crash Handling
FT-2: Stale Results Protection
"""

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from GlassOrchestrator import (
    run_pipeline,
    validate_results_freshness,
    phase2_parse,
    phase3_worker,
)


# ─── FT-1: Worker Crash Handling ─────────────────────────────────────────────


class TestFT1_WorkerCrashHandling:
    """GPO must stop immediately on worker failure — no email, no Excel update."""

    def test_pipeline_aborts_on_worker_failure(self, tmp_path, monkeypatch):
        """Simulate GlassDataParser.py returning exit code 1.
        Pipeline must not reach Phase 5 (persist) or Phase 6 (notify)."""

        # Create a fake worker script that exits with error
        bad_worker = tmp_path / "GlassDataParser.py"
        bad_worker.write_text("import sys; sys.exit(1)\n")

        # Patch configuration to use temp paths
        monkeypatch.setattr("GlassOrchestrator.WORKER_SCRIPT", bad_worker)
        monkeypatch.setattr("GlassOrchestrator.DATA_DIR", tmp_path)
        monkeypatch.setattr("GlassOrchestrator.CSV_PATH", tmp_path / "GlassDataParser.csv")

        # Phase 3 should raise CalledProcessError
        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            phase3_worker(["59340120", "59340121"])
        assert exc_info.value.returncode == 1

    def test_full_pipeline_stops_after_worker_crash(self, tmp_path, monkeypatch):
        """Run full pipeline with a crashing worker — Phase 5/6 must NOT execute."""
        bad_worker = tmp_path / "GlassDataParser.py"
        bad_worker.write_text("import sys; sys.exit(1)\n")

        monkeypatch.setattr("GlassOrchestrator.WORKER_SCRIPT", bad_worker)
        monkeypatch.setattr("GlassOrchestrator.DATA_DIR", tmp_path)
        monkeypatch.setattr("GlassOrchestrator.CSV_PATH", tmp_path / "GlassDataParser.csv")

        # Mock Phase 1 to return test data (bypass Gmail)
        mock_descriptions = ["59340120", "59340121r"]
        mock_date = datetime(2026, 3, 5)
        monkeypatch.setattr(
            "GlassOrchestrator.phase1_input",
            lambda: (mock_descriptions, mock_date),
        )

        # Track whether Phase 5 / Phase 6 are called
        persist_called = False
        notify_called = False
        original_persist = __import__("GlassOrchestrator").phase5_persist
        original_notify = __import__("GlassOrchestrator").phase6_notify

        def spy_persist(df):
            nonlocal persist_called
            persist_called = True
            return original_persist(df)

        def spy_notify(df):
            nonlocal notify_called
            notify_called = True
            return original_notify(df)

        monkeypatch.setattr("GlassOrchestrator.phase5_persist", spy_persist)
        monkeypatch.setattr("GlassOrchestrator.phase6_notify", spy_notify)

        # Run the pipeline — should not crash, but should abort after Phase 3
        run_pipeline()

        assert not persist_called, "Phase 5 should NOT have been called after worker crash"
        assert not notify_called, "Phase 6 should NOT have been called after worker crash"


# ─── FT-2: Stale Results Protection ──────────────────────────────────────────


class TestFT2_StaleResultsProtection:
    """GPO must detect stale GlassResults.txt and throw a fatal error."""

    def test_fresh_file_passes(self, tmp_path):
        """A file modified just now should pass validation."""
        results = tmp_path / "GlassResults.txt"
        results.write_text("MVA,VIN,Desc\n59340120,ABC123,Windshield\n")
        # File was just created → fresh
        validate_results_freshness(results, max_age_seconds=300)  # should not raise

    def test_stale_file_raises(self, tmp_path):
        """A file last modified >24h ago must raise RuntimeError."""
        results = tmp_path / "GlassResults.txt"
        results.write_text("MVA,VIN,Desc\n59340120,ABC123,Windshield\n")

        # Backdate the file's mtime by 25 hours
        old_time = time.time() - (25 * 3600)
        os.utime(str(results), (old_time, old_time))

        with pytest.raises(RuntimeError, match="Stale results file"):
            validate_results_freshness(results, max_age_seconds=300)

    def test_missing_file_raises(self, tmp_path):
        """No results file at all → RuntimeError."""
        with pytest.raises(RuntimeError, match="Results file not found"):
            validate_results_freshness(tmp_path / "nonexistent.txt")

    def test_pipeline_aborts_on_stale_results(self, tmp_path, monkeypatch):
        """Full pipeline: stale results → ABORT before Phase 4."""
        results_file = tmp_path / "GlassResults.txt"
        results_file.write_text("MVA,VIN,Desc\n59340120,ABC123,Windshield\n")

        # Backdate mtime
        old_time = time.time() - (25 * 3600)
        os.utime(str(results_file), (old_time, old_time))

        # Create a worker that "succeeds" but leaves a stale file
        ok_worker = tmp_path / "GlassDataParser.py"
        ok_worker.write_text("pass\n")  # exits 0 but doesn't update results

        monkeypatch.setattr("GlassOrchestrator.WORKER_SCRIPT", ok_worker)
        monkeypatch.setattr("GlassOrchestrator.RESULTS_PATH", results_file)
        monkeypatch.setattr("GlassOrchestrator.DATA_DIR", tmp_path)
        monkeypatch.setattr("GlassOrchestrator.CSV_PATH", tmp_path / "GlassDataParser.csv")

        mock_descriptions = ["59340120"]
        mock_date = datetime(2026, 3, 5)
        monkeypatch.setattr(
            "GlassOrchestrator.phase1_input",
            lambda: (mock_descriptions, mock_date),
        )

        merge_called = False
        original_merge = __import__("GlassOrchestrator").phase4_merge

        def spy_merge(manifest):
            nonlocal merge_called
            merge_called = True
            return original_merge(manifest)

        monkeypatch.setattr("GlassOrchestrator.phase4_merge", spy_merge)

        run_pipeline()

        assert not merge_called, "Phase 4 should NOT execute when results are stale"
