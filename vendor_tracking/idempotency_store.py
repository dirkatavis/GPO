"""Idempotency store for vendor tracking email processing.

Persists processed email Message-IDs to a JSON file so that re-runs
do not produce duplicate sheet writes.

File format: {"processed": ["<msg-id-1>", "<msg-id-2>", ...]}
"""

import json
import logging
from pathlib import Path

log = logging.getLogger("vendor_tracking.idempotency_store")

_KEY = "processed"


class IdempotencyStore:
    """Persist and check processed email Message-IDs across runs."""

    def __init__(self, store_path: Path) -> None:
        self._path = store_path
        self._ids: set[str] = set()
        self._load()

    # ─── Public API ──────────────────────────────────────────────────────────

    def is_processed(self, message_id: str) -> bool:
        """Return True if this Message-ID has already been processed."""
        return message_id.strip() in self._ids

    def mark_processed(self, message_id: str) -> None:
        """Record a Message-ID as processed and flush to disk."""
        mid = message_id.strip()
        if mid in self._ids:
            return
        self._ids.add(mid)
        self._save()
        log.debug("Marked processed: %s", mid)

    def __len__(self) -> int:
        return len(self._ids)

    # ─── Persistence ─────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.exists():
            log.debug("Idempotency store not found at %s — starting fresh", self._path)
            return
        try:
            with self._path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get(_KEY), list):
                self._ids = set(data[_KEY])
                log.debug("Loaded %d processed Message-IDs from %s", len(self._ids), self._path)
            else:
                log.warning("Idempotency store at %s has unexpected format — resetting", self._path)
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("Could not load idempotency store from %s: %s — starting fresh", self._path, exc)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", encoding="utf-8") as f:
                json.dump({_KEY: sorted(self._ids)}, f, indent=2)
        except OSError as exc:
            log.error("Could not save idempotency store to %s: %s", self._path, exc)
