"""ScanPage tests using fixture HTML loaded into a real Page."""
import pytest

from src.compass_go.pages.scan_page import ScanPage
from tests.compass_go.fixtures import SCAN_VEHICLE_HTML

pytestmark = pytest.mark.browser

pytest.importorskip("playwright.sync_api")


@pytest.fixture
def page():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        pg = context.new_page()
        yield pg
        context.close()
        browser.close()


def test_is_displayed_true_when_scan_container_present(page):
    page.set_content(SCAN_VEHICLE_HTML)

    assert ScanPage(page).is_displayed() is True


def test_submit_fills_input_and_clicks_enter(page):
    page.set_content(SCAN_VEHICLE_HTML)
    page.evaluate(
        """() => {
            const btn = [...document.querySelectorAll('button')]
                .find(b => b.textContent.trim() === 'Enter');
            btn.addEventListener('click', () => {
                const i = document.querySelector('input[aria-label="Or enter MVA/VIN"]');
                document.title = 'SUBMITTED:' + i.value;
                document.body.insertAdjacentHTML('beforeend', '<h1>Vehicle Details</h1>');
            });
        }"""
    )

    ScanPage(page).submit("058883134")

    assert page.title() == "SUBMITTED:058883134"
