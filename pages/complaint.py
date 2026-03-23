# FILE: pages/complaint.py
# PASTE THIS FULL FILE

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

Status = Literal["Open", "Closed"]


@dataclass(slots=True)
class Complaint:
    """Generic domain object for a single Complaint."""

    id: str
    type: str
    status: Status
    created_at: Optional[datetime] = None

    def is_open(self) -> bool:
        return self.status.lower() == "open"

    def is_closed(self) -> bool:
        return self.status.lower() == "closed"

    def age_in_days(self) -> Optional[int]:
        """Return age in days since creation, or None if no created_at."""
        if not self.created_at:
            return None
        return (datetime.now() - self.created_at).days
