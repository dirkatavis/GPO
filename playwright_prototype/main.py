import argparse
import asyncio
import csv
import logging
import sys
from pathlib import Path

from playwright.async_api import async_playwright

from playwright_prototype.config import resolve_headless, resolve_step_delay
from playwright_prototype.session import ensure_authenticated_context
from playwright_prototype.steps import (
    click_add_work_item,
    complete_mileage_dialog,
    confirm_completion,
    create_work_item,
    handle_complaint_dialog,
    navigate_to_mva,
    select_glass_opcode,
    warmup_compass,
)

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV = Path(__file__).resolve().parent / "sample_mvas.csv"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(BASE_DIR / "playwright_prototype.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("playwright_prototype")


def load_csv(path: Path) -> list[dict]:
    """Load rows from a CSV file with columns: mva, location, action.

    location and action default to WS and Replace when blank.
    Rows with no mva value are skipped.
    """
    if not path.exists():
        log.error("CSV not found: %s", path)
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            mva = (row.get("mva") or "").strip()
            if not mva:
                log.warning("Row %d: blank mva — skipping", i)
                continue
            rows.append({
                "mva": mva,
                "location": (row.get("location") or "WS").strip(),
                "action": (row.get("action") or "Replace").strip(),
            })
    return rows


async def process_mva(page, mva: str, location: str, action: str, step_delay_ms: int = 0) -> None:
    """Run the full work-item creation flow for a single MVA."""
    async def delay():
        if step_delay_ms:
            await page.wait_for_timeout(step_delay_ms)

    await navigate_to_mva(page, mva);                                        await delay()
    await click_add_work_item(page, mva);                                    await delay()
    await handle_complaint_dialog(page, mva, location, action, step_delay_ms); await delay()
    await complete_mileage_dialog(page, mva);                                await delay()
    await select_glass_opcode(page);                                         await delay()
    await create_work_item(page);                                            await delay()
    await confirm_completion(page)


async def main(csv_path: Path = DEFAULT_CSV, pause: bool = False) -> int:
    headless = resolve_headless()
    step_delay_ms = resolve_step_delay()
    rows = load_csv(csv_path)
    if not rows:
        log.error("No rows loaded from %s — aborting", csv_path)
        return 1

    log.info("Starting Playwright prototype — %d MVA(s) | headless=%s | step_delay=%dms",
             len(rows), headless, step_delay_ms)

    async with async_playwright() as pw:
        launch_args = ["--disable-blink-features=AutomationControlled"]
        if not headless:
            launch_args.append("--start-maximized")
        browser = await pw.chromium.launch(headless=headless, args=launch_args)
        try:
            context, page = await ensure_authenticated_context(browser, no_viewport=not headless)

            await warmup_compass(page)

            if pause:
                row = rows[0]
                mva, location, action = row["mva"], row["location"], row["action"]
                log.info("[MAIN] --pause stepping through MVA %s", mva)

                async def step(coro, label: str):
                    await coro
                    log.info("[MAIN] %s — pausing", label)
                    await page.pause()

                await step(navigate_to_mva(page, mva),                          "Step 1: navigated to MVA")
                await step(click_add_work_item(page, mva),                       "Step 2: Add Work Item clicked")
                await step(handle_complaint_dialog(page, mva, location, action, step_delay_ms), "Step 3: complaint dialog handled")
                await step(complete_mileage_dialog(page, mva),                   "Step 4: mileage dialog advanced")
                await step(select_glass_opcode(page),                            "Step 5: Glass opcode selected")
                await step(create_work_item(page),                               "Step 6: Create Work Item clicked")
                await step(confirm_completion(page),                             "Step 7: Done clicked — work item created")
                return 0

            summary = {"processed": 0, "created": 0, "failed": 0}
            for row in rows:
                mva = row["mva"]
                summary["processed"] += 1
                try:
                    await process_mva(page, mva, row["location"], row["action"], step_delay_ms)
                    summary["created"] += 1
                    log.info("[MAIN] %s — work item created", mva)
                except Exception:
                    log.exception("[MAIN] %s — failed", mva)
                    summary["failed"] += 1

            log.info("Run complete — processed=%d created=%d failed=%d",
                     summary["processed"], summary["created"], summary["failed"])
            return 0 if summary["failed"] == 0 else 1

        except Exception:
            log.exception("Prototype failed during setup.")
            return 1
        finally:
            await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Playwright prototype — Compass work item creation")
    parser.add_argument("--fresh", action="store_true", help="Delete storage_state.json before running to force a full login")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Path to MVA CSV file")
    parser.add_argument("--pause", action="store_true", help="Step through each action with Playwright Inspector pauses")
    args = parser.parse_args()

    if args.fresh:
        from playwright_prototype.config import STORAGE_STATE_PATH
        if STORAGE_STATE_PATH.exists():
            STORAGE_STATE_PATH.unlink()
            print(f"Deleted {STORAGE_STATE_PATH} — will perform full login")

    sys.exit(asyncio.run(main(csv_path=args.csv, pause=args.pause)))
