# FILE: pages/vehicle.py
# PASTE THIS FULL FILE

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class Vehicle:
    """Generic domain object for a vehicle record (from MVA lookup)."""

    mva: str
    plate: Optional[str] = None
    purchase_date: Optional[datetime] = None
    vin: Optional[str] = None
    desc: Optional[str] = None
    region_brand: Optional[str] = None
    car_class_code: Optional[str] = None
    last_revenue: Optional[datetime] = None
    reg_exp_date: Optional[datetime] = None
    lighthouse: Optional[str] = None
    unrentable: Optional[str] = None
    last_scan_geo: Optional[str] = None
    last_scan_date: Optional[datetime] = None
    odometer: Optional[int] = None
    last_pm_mileage: Optional[int] = None
    next_pm_mileage: Optional[int] = None
    pm_interval: Optional[int] = None
    wizard_status: Optional[str] = None
    oos_indicator: Optional[bool] = None
    oos_reason: Optional[str] = None
    turnback_status: Optional[str] = None
    alert_status_reason: Optional[str] = None
    trunk_key: Optional[str] = None

    def age_in_days(self) -> Optional[int]:
        """Return age in days since purchase, or None if purchase_date is missing."""
        if not self.purchase_date:
            return None
        return (datetime.now() - self.purchase_date).days
