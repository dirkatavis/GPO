"""Local JSON-backed tracker for MVA cycle-day metrics."""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile


log = logging.getLogger("GlassOrchestrator.CycleTracker")


class CycleTracker:
    """Track active MVAs and cycle length across daily snapshots.

    Cycle length increments by one for each snapshot day where the MVA appears.
    If an MVA disappears from the current snapshot, its cycle is closed.
    If an MVA reappears after a gap larger than the configured grace, a new cycle starts.
    """

    def __init__(
        self,
        store_path: Path,
        gap_grace_days: int = 1,
        completed_retention: int = 1000,
    ) -> None:
        self.store_path = Path(store_path)
        self.gap_grace_days = max(0, int(gap_grace_days))
        self.completed_retention = max(0, int(completed_retention))

    def record_snapshot(self, mvas: list[str], snapshot_date: date) -> dict[str, int]:
        """Record one run snapshot and return cycle days keyed by active MVA."""
        state = self._load_state()
        snapshot_iso = snapshot_date.isoformat()
        last_snapshot = state.get("last_snapshot_date")
        if isinstance(last_snapshot, str) and last_snapshot:
            last_snapshot_date = self._parse_date(last_snapshot)
            if snapshot_date < last_snapshot_date:
                # Ignore out-of-order runs so older emails/reruns cannot corrupt chronology.
                log.warning(
                    "Ignoring out-of-order snapshot %s (latest recorded %s)",
                    snapshot_iso,
                    last_snapshot,
                )
                active = state.get("active", {})
                return {mva: int(active[mva]["days"]) for mva in sorted(set(mvas)) if mva in active}

        observed = sorted(set(mvas))

        active = state.setdefault("active", {})
        completed = state.setdefault("completed", [])
        days_by_mva: dict[str, int] = {}

        for mva in observed:
            record = active.get(mva)
            if record is None:
                record = {
                    "first_seen": snapshot_iso,
                    "last_seen": snapshot_iso,
                    "days": 1,
                }
            else:
                last_seen = self._parse_date(record["last_seen"])
                gap_days = (snapshot_date - last_seen).days
                if gap_days == 0:
                    # Same-day rerun is idempotent for cycle-day counting.
                    pass
                elif gap_days <= (self.gap_grace_days + 1):
                    record["last_seen"] = snapshot_iso
                    record["days"] = int(record.get("days", 0)) + 1
                else:
                    completed.append(
                        {
                            "mva": mva,
                            "first_seen": record["first_seen"],
                            "last_seen": record["last_seen"],
                            "days": int(record.get("days", 0)),
                            "closed_reason": "gap_reset",
                            "closed_at": snapshot_iso,
                        }
                    )
                    record = {
                        "first_seen": snapshot_iso,
                        "last_seen": snapshot_iso,
                        "days": 1,
                    }

            active[mva] = record
            days_by_mva[mva] = int(record["days"])

        now_missing = [mva for mva in list(active.keys()) if mva not in days_by_mva]
        for mva in now_missing:
            record = active.pop(mva)
            completed.append(
                {
                    "mva": mva,
                    "first_seen": record["first_seen"],
                    "last_seen": record["last_seen"],
                    "days": int(record.get("days", 0)),
                    "closed_reason": "not_seen",
                    "closed_at": snapshot_iso,
                }
            )

        state["active"] = active
        # Long-term completed-cycle history is intentional for trend analysis and
        # auditability, with growth controlled via the configured retention cap.
        state["completed"] = completed[-self.completed_retention :] if self.completed_retention else []
        state["last_snapshot_date"] = snapshot_iso
        self._save_state(state)
        return days_by_mva

    def get_active_cycles(self) -> dict[str, dict]:
        """Return active cycles currently tracked in the JSON store."""
        return self._load_state().get("active", {})

    def _load_state(self) -> dict:
        if not self.store_path.exists():
            return {"version": 1, "active": {}, "completed": [], "last_snapshot_date": None}
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                return {"version": 1, "active": {}, "completed": [], "last_snapshot_date": None}
            loaded.setdefault("version", 1)
            loaded.setdefault("active", {})
            loaded.setdefault("completed", [])
            loaded.setdefault("last_snapshot_date", None)
            return loaded
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            if self.store_path.exists():
                quarantine_path = self.store_path.with_suffix(
                    f".corrupt.{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.json"
                )
                try:
                    self.store_path.rename(quarantine_path)
                    log.warning(
                        "Cycle tracker state was unreadable and has been quarantined: %s (%s)",
                        quarantine_path,
                        exc,
                    )
                except OSError:
                    log.warning("Cycle tracker state unreadable; reset to empty (%s)", exc)
            return {"version": 1, "active": {}, "completed": [], "last_snapshot_date": None}

    def _save_state(self, state: dict) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: str | None = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.store_path.parent,
                prefix=f"{self.store_path.stem}.",
                suffix=".tmp",
                delete=False,
            ) as f:
                json.dump(state, f, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
                temp_path = f.name

            os.replace(temp_path, self.store_path)
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    @staticmethod
    def _parse_date(value: str) -> date:
        return datetime.strptime(value, "%Y-%m-%d").date()
