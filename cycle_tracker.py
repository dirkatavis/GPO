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
            last_snapshot_date = self._try_parse_date(last_snapshot)
            if last_snapshot_date is None:
                log.warning("Invalid last_snapshot_date in tracker state: %s", last_snapshot)
                state["last_snapshot_date"] = None
            elif snapshot_date < last_snapshot_date:
                # Ignore out-of-order runs so older emails/reruns cannot corrupt chronology.
                log.warning(
                    "Ignoring out-of-order snapshot %s (latest recorded %s)",
                    snapshot_iso,
                    last_snapshot,
                )
                active = state.get("active", {})
                return {
                    mva: int(active[mva]["days"])
                    for mva in sorted(set(mvas))
                    if mva in active and isinstance(active[mva], dict)
                }

        observed = sorted(set(mvas))
        active = state.setdefault("active", {})
        completed = state.setdefault("completed", [])
        days_by_mva: dict[str, int] = {}

        for mva in observed:
            record = active.get(mva)
            if not isinstance(record, dict):
                record = self._new_cycle_record(snapshot_iso)
            else:
                first_seen = self._try_parse_date(record.get("first_seen"))
                last_seen = self._try_parse_date(record.get("last_seen"))
                current_days = self._coerce_positive_int(record.get("days"), default=1)

                if first_seen is None or last_seen is None:
                    log.warning("Invalid active cycle record for MVA %s; resetting cycle", mva)
                    record = self._new_cycle_record(snapshot_iso)
                else:
                    gap_days = (snapshot_date - last_seen).days
                    if gap_days == 0:
                        # Same-day rerun is idempotent for cycle-day counting.
                        pass
                    elif gap_days <= (self.gap_grace_days + 1):
                        record["last_seen"] = snapshot_iso
                        record["days"] = current_days + 1
                    else:
                        completed.append(
                            {
                                "mva": mva,
                                "first_seen": str(record.get("first_seen", snapshot_iso)),
                                "last_seen": str(record.get("last_seen", snapshot_iso)),
                                "days": current_days,
                                "closed_reason": "gap_reset",
                                "closed_at": snapshot_iso,
                            }
                        )
                        record = self._new_cycle_record(snapshot_iso)

            active[mva] = record
            days_by_mva[mva] = self._coerce_positive_int(record.get("days"), default=1)

        now_missing = [mva for mva in list(active.keys()) if mva not in days_by_mva]
        for mva in now_missing:
            record = active.pop(mva)
            if not isinstance(record, dict):
                continue
            completed.append(
                {
                    "mva": mva,
                    "first_seen": str(record.get("first_seen", snapshot_iso)),
                    "last_seen": str(record.get("last_seen", snapshot_iso)),
                    "days": self._coerce_positive_int(record.get("days"), default=1),
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
            return self._empty_state()

        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            normalized, dropped = self._normalize_state(loaded)
            if dropped:
                log.warning("Cycle tracker state normalized; dropped %d invalid record(s)", dropped)
            return normalized
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            self._quarantine_state_file(exc)
            return self._empty_state()

    def _normalize_state(self, loaded: object) -> tuple[dict, int]:
        if not isinstance(loaded, dict):
            raise ValueError("Cycle tracker state root must be a JSON object")

        dropped = 0
        state = self._empty_state()

        version_value = loaded.get("version", 1)
        state["version"] = version_value if isinstance(version_value, int) else 1

        last_snapshot_value = loaded.get("last_snapshot_date")
        if isinstance(last_snapshot_value, str) and self._try_parse_date(last_snapshot_value):
            state["last_snapshot_date"] = last_snapshot_value
        elif last_snapshot_value not in (None, ""):
            dropped += 1

        active_value = loaded.get("active", {})
        if isinstance(active_value, dict):
            for mva, record in active_value.items():
                if not isinstance(mva, str) or not isinstance(record, dict):
                    dropped += 1
                    continue

                first_seen = record.get("first_seen")
                last_seen = record.get("last_seen")
                days = self._coerce_positive_int(record.get("days"), default=1)

                if not (isinstance(first_seen, str) and isinstance(last_seen, str)):
                    dropped += 1
                    continue
                if not self._try_parse_date(first_seen) or not self._try_parse_date(last_seen):
                    dropped += 1
                    continue

                state["active"][mva] = {
                    "first_seen": first_seen,
                    "last_seen": last_seen,
                    "days": days,
                }
        else:
            dropped += 1

        completed_value = loaded.get("completed", [])
        if isinstance(completed_value, list):
            for item in completed_value:
                if isinstance(item, dict):
                    state["completed"].append(item)
                else:
                    dropped += 1
        elif completed_value is not None:
            dropped += 1

        return state, dropped

    @staticmethod
    def _new_cycle_record(snapshot_iso: str) -> dict[str, str | int]:
        return {
            "first_seen": snapshot_iso,
            "last_seen": snapshot_iso,
            "days": 1,
        }

    @staticmethod
    def _coerce_positive_int(value: object, default: int = 1) -> int:
        try:
            parsed = int(value)
            return parsed if parsed > 0 else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _empty_state() -> dict:
        return {"version": 1, "active": {}, "completed": [], "last_snapshot_date": None}

    def _quarantine_state_file(self, exc: Exception) -> None:
        if not self.store_path.exists():
            return
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
    def _try_parse_date(value: object) -> date | None:
        if not isinstance(value, str):
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None
