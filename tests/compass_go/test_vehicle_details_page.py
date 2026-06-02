"""VehicleDetailsPage tests using a fixture HTML loaded into a real Page.

Requires Playwright + a Chromium install (`playwright install chromium`).
Marked as 'browser' so they can be skipped in CI environments without browsers.
"""
import pytest

from src.compass_go.pages.vehicle_details_page import (
    DATA_KEY_VIN,
    VehicleDetailsPage,
)
from tests.compass_go.fixtures import VEHICLE_DETAILS_EXPANDED_HTML

pytestmark = pytest.mark.browser

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture
def page():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        yield page
        context.close()
        browser.close()


def test_read_vin_from_fixture(page):
    page.set_content(VEHICLE_DETAILS_EXPANDED_HTML)
    details = VehicleDetailsPage(page)

    assert details.read(DATA_KEY_VIN) == "5XYP64GC1SG682257"
