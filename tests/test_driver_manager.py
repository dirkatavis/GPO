import pytest
from selenium.common.exceptions import WebDriverException
from unittest.mock import Mock

from core import driver_manager as dm


@pytest.fixture(autouse=True)
def reset_driver_state():
    dm.quit_driver()
    yield
    dm.quit_driver()


def test_create_driver_uses_selenium_manager_as_primary(monkeypatch):
    monkeypatch.setattr(dm, "get_browser_version", lambda: "146.0.3856.62")
    monkeypatch.setattr(dm, "get_driver_version", lambda path: "145.0.3800.82")

    calls = []
    created_driver = Mock()

    def fake_edge(**kwargs):
        calls.append({"service": kwargs.get("service")})
        return created_driver

    monkeypatch.setattr(dm.webdriver, "Edge", fake_edge)

    assert dm.create_driver() is created_driver
    assert len(calls) == 1
    assert calls[0]["service"] is None


def test_create_driver_does_not_probe_bundled_driver_when_manager_succeeds(monkeypatch):
    monkeypatch.setattr(dm, "get_browser_version", lambda: "146.0.3856.62")

    def fail_if_called(_path):
        raise AssertionError("bundled driver should not be probed on successful Selenium Manager launch")

    monkeypatch.setattr(dm, "get_driver_version", fail_if_called)
    monkeypatch.setattr(dm.webdriver, "Edge", lambda **kwargs: Mock())

    driver = dm.create_driver()
    assert driver is not None


def test_create_driver_falls_back_to_bundled_when_manager_fails(monkeypatch):
    monkeypatch.setattr(dm, "get_browser_version", lambda: "146.0.3856.62")
    monkeypatch.setattr(dm, "get_driver_version", lambda path: "146.0.3856.1")

    calls = []
    bundled_service = object()
    created_driver = Mock()
    responses = iter([WebDriverException("manager failed"), created_driver])

    monkeypatch.setattr(dm, "Service", lambda path: bundled_service)

    def fake_edge(**kwargs):
        calls.append({"service": kwargs.get("service")})
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(dm.webdriver, "Edge", fake_edge)

    assert dm.create_driver() is created_driver
    assert len(calls) == 2
    assert calls[0]["service"] is None
    assert calls[1]["service"] is bundled_service
