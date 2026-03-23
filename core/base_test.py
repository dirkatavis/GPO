import pytest

from core.driver_manager import create_driver, get_driver, quit_driver


@pytest.fixture
def driver():
    """Fixture to initialize and quit the WebDriver."""
    # Create a new driver instance
    driver = create_driver()
    driver.maximize_window()
    driver.implicitly_wait(10)
    yield driver
    # Properly clean up the driver
    quit_driver()
