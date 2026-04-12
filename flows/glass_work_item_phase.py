# Phase 7 — Compass Work Item Creation
# Standalone script — not part of the main GlassOrchestrator pipeline.
# Reads from GlassClaims sheet, creates Compass work items for eligible MVAs.
#
# KNOWN LIMITATION: Location defaults to WINDSHIELD for all rows.
# Side/rear damage is rare and handled manually by the operator.
# When Orca scan data includes location, update read_glass_claims() to parse it.
#
# ARCHITECTURE NOTE: Designed for extraction into the unified automation repo.
# Manifest contract (list of plain dicts) and return contract (summary dict) are portable.
# WorkItemHandler subclasses are the extension point — not this orchestrator.

from utils.logger import log
from core.eligibility import is_notification_eligible
from flows.work_item_flow import check_existing_work_item
from flows.work_item_handler import WorkItemConfig, create_work_item_handler


def read_glass_claims(sheet_client, tab_name: str = "GlassClaims") -> list[dict]:
    """
    Read eligible, unprocessed rows from the GlassClaims sheet tab.

    Filters:
    - is_notification_eligible(row) == True  (Replacement only)
    - WorkItemCreated column is blank

    Returns list of dicts with keys: mva, damage_type, location.
    Location defaults to WINDSHIELD when blank.
    """
    rows = sheet_client.get_all_records()
    result = []
    for row in rows:
        if not is_notification_eligible(row):
            continue
        if row.get("WorkItemCreated", "").strip():
            continue
        result.append({
            "mva": row["MVA"],
            "damage_type": row.get("Damage Type") or row.get("damage_type", "Replacement"),
            "location": row.get("Location") or "WINDSHIELD",
        })
    return result


def run_glass_work_item_phase(driver, manifest: list[dict], sheet_client=None,
                               tab_name: str = "GlassClaims") -> dict:
    """
    Process each MVA in the manifest: check for existing work item, create if missing.

    Never aborts the loop — all MVAs are attempted regardless of prior failures.

    Args:
        driver: Selenium WebDriver instance
        manifest: list of dicts with keys mva, damage_type, location
        sheet_client: optional sheet client; if provided, marks WorkItemCreated=Y on success
        tab_name: GlassClaims tab name (passed to sheet_client)

    Returns:
        dict with keys: processed, created, skipped, failed
    """
    summary = {"processed": 0, "created": 0, "skipped": 0, "failed": 0}

    for entry in manifest:
        mva = entry["mva"]
        summary["processed"] += 1
        try:
            log.info(f"[PHASE7] {mva} - Starting work item review")

            if check_existing_work_item(driver, mva, work_item_type="GLASS"):
                log.info(f"[PHASE7] {mva} - Open glass work item already exists, skipping")
                summary["skipped"] += 1
                continue

            config = WorkItemConfig(
                mva=mva,
                damage_type=entry.get("damage_type"),
                location=entry.get("location"),
            )
            handler = create_work_item_handler("GLASS", driver)
            result = handler.create_work_item(config)

            if result.get("status") == "created":
                log.info(f"[PHASE7] {mva} - Work item created successfully")
                summary["created"] += 1
                if sheet_client is not None:
                    sheet_client.mark_work_item_created(mva, tab_name)
            else:
                log.error(f"[PHASE7] {mva} - Work item creation failed: {result}")
                summary["failed"] += 1

        except Exception as e:
            log.error(f"[PHASE7][ERROR] {mva} - {e}")
            summary["failed"] += 1

    return summary
