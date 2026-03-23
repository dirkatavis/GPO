# FILE: pages/work_item.py
# PASTE THIS FULL FILE

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

Status = Literal["Open", "Complete"]


@dataclass(slots=True)
class WorkItem:
    """Generic domain object for a single Work Item."""

    id: str
    type: str
    status: Status
    completed_at: Optional[datetime] = None

    def is_open(self) -> bool:
        return self.status.lower() == "open"

    def is_complete(self) -> bool:
        return self.status.lower() == "complete"

    def age_in_days(self) -> Optional[int]:
        """Return age in days since completion, or None if no completed_at."""
        if not self.completed_at:
            return None
        return (datetime.now() - self.completed_at).days
