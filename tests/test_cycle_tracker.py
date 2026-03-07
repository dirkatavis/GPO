"""Unit tests for JSON-backed MVA cycle-day tracking."""

from datetime import date, timedelta

from cycle_tracker import CycleTracker


def test_cycle_tracker_moves_from_day1_to_day2(tmp_path):
    store = tmp_path / "mva_cycle_tracker.json"
    tracker = CycleTracker(store_path=store, gap_grace_days=1)

    day1 = date(2026, 3, 5)
    run1 = tracker.record_snapshot(["12345678"], day1)
    assert run1 == {"12345678": 1}

    day2 = day1 + timedelta(days=1)
    run2 = tracker.record_snapshot(["12345678"], day2)
    assert run2 == {"12345678": 2}

    active = tracker.get_active_cycles()
    assert active["12345678"]["first_seen"] == "2026-03-05"
    assert active["12345678"]["last_seen"] == "2026-03-06"
    assert active["12345678"]["days"] == 2


def test_cycle_tracker_closes_when_mva_disappears(tmp_path):
    store = tmp_path / "mva_cycle_tracker.json"
    tracker = CycleTracker(store_path=store, gap_grace_days=1)

    day1 = date(2026, 3, 5)
    tracker.record_snapshot(["12345678"], day1)

    day2 = day1 + timedelta(days=1)
    tracker.record_snapshot([], day2)

    active = tracker.get_active_cycles()
    assert "12345678" not in active


def test_cycle_tracker_resets_after_gap_beyond_grace(tmp_path):
    store = tmp_path / "mva_cycle_tracker.json"
    tracker = CycleTracker(store_path=store, gap_grace_days=1)

    day1 = date(2026, 3, 5)
    tracker.record_snapshot(["12345678"], day1)

    day4 = day1 + timedelta(days=3)
    run = tracker.record_snapshot(["12345678"], day4)

    assert run["12345678"] == 1
    active = tracker.get_active_cycles()
    assert active["12345678"]["first_seen"] == "2026-03-08"


def test_cycle_tracker_same_day_snapshot_is_idempotent(tmp_path):
    store = tmp_path / "mva_cycle_tracker.json"
    tracker = CycleTracker(store_path=store, gap_grace_days=7)

    day1 = date(2026, 3, 5)
    first = tracker.record_snapshot(["12345678"], day1)
    second = tracker.record_snapshot(["12345678"], day1)

    assert first["12345678"] == 1
    assert second["12345678"] == 1

    active = tracker.get_active_cycles()
    assert active["12345678"]["last_seen"] == "2026-03-05"
    assert active["12345678"]["days"] == 1


def test_cycle_tracker_ignores_out_of_order_snapshot(tmp_path):
    store = tmp_path / "mva_cycle_tracker.json"
    tracker = CycleTracker(store_path=store, gap_grace_days=7)

    day2 = date(2026, 3, 6)
    tracker.record_snapshot(["12345678"], day2)

    day1 = date(2026, 3, 5)
    result = tracker.record_snapshot(["12345678"], day1)

    # Out-of-order run should be ignored and existing chronology preserved.
    assert result["12345678"] == 1
    active = tracker.get_active_cycles()
    assert active["12345678"]["first_seen"] == "2026-03-06"
    assert active["12345678"]["last_seen"] == "2026-03-06"
    assert active["12345678"]["days"] == 1


def test_cycle_tracker_persists_across_instances(tmp_path):
    store = tmp_path / "mva_cycle_tracker.json"

    tracker_run1 = CycleTracker(store_path=store, gap_grace_days=7)
    day1 = date(2026, 3, 5)
    assert tracker_run1.record_snapshot(["12345678"], day1)["12345678"] == 1

    # Simulate a new process/run by constructing a new tracker instance.
    tracker_run2 = CycleTracker(store_path=store, gap_grace_days=7)
    day2 = date(2026, 3, 6)
    assert tracker_run2.record_snapshot(["12345678"], day2)["12345678"] == 2


def test_cycle_tracker_ignores_invalid_active_record_in_loaded_state(tmp_path):
    store = tmp_path / "mva_cycle_tracker.json"
    store.write_text(
        '{"version":1,"active":{"12345678":{"first_seen":"2026-03-05","last_seen":"BAD_DATE","days":2}},"completed":[],"last_snapshot_date":"2026-03-05"}',
        encoding="utf-8",
    )

    tracker = CycleTracker(store_path=store, gap_grace_days=7)
    day2 = date(2026, 3, 6)
    result = tracker.record_snapshot(["12345678"], day2)

    # Invalid loaded record should be sanitized/reset instead of crashing tracking.
    assert result["12345678"] == 1
