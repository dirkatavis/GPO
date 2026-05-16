import pytest

from utils import ui_helpers


class _FakeDriver:
    current_url = "https://example.test/login"
    title = "Login"

    def execute_script(self, script):
        # ui_helpers calls execute_script for both readyState and activeElement snapshots.
        if "document.readyState" in script:
            return "complete"
        return {"tag": "INPUT", "id": "fake"}

    def find_elements(self, *_):
        return []


def test_should_capture_timeout_artifacts_defaults_to_false(monkeypatch):
    monkeypatch.delenv("GLASS_CAPTURE_TIMEOUT_ARTIFACTS", raising=False)

    assert ui_helpers._should_capture_timeout_artifacts() is False


@pytest.mark.parametrize("value", ["1", "true", "YES", "on"])
def test_should_capture_timeout_artifacts_true_values(monkeypatch, value):
    monkeypatch.setenv("GLASS_CAPTURE_TIMEOUT_ARTIFACTS", value)

    assert ui_helpers._should_capture_timeout_artifacts() is True


def test_log_send_text_timeout_diagnostics_artifact_capture_is_opt_in(monkeypatch):
    captured = []

    monkeypatch.delenv("GLASS_CAPTURE_TIMEOUT_ARTIFACTS", raising=False)
    monkeypatch.setattr(
        ui_helpers,
        "_dump_artifacts",
        lambda driver, prefix=None: captured.append((driver, prefix)),
    )

    ui_helpers._log_send_text_timeout_diagnostics(
        _FakeDriver(), ("id", "wwid"), "E96693"
    )

    assert captured == []
