from utils import ui_helpers


class _FakeDriver:
    current_url = "https://example.test/login"
    title = "Login"

    def execute_script(self, script):
        if "document.readyState" in script:
            return "complete"
        return {"tag": "INPUT", "id": "fake"}

    def find_elements(self, *_):
        return []


def test_should_capture_timeout_artifacts_defaults_to_false(monkeypatch):
    monkeypatch.delenv("GLASS_CAPTURE_TIMEOUT_ARTIFACTS", raising=False)

    assert ui_helpers._should_capture_timeout_artifacts() is False


def test_should_capture_timeout_artifacts_true_values(monkeypatch):
    monkeypatch.setenv("GLASS_CAPTURE_TIMEOUT_ARTIFACTS", "YES")

    assert ui_helpers._should_capture_timeout_artifacts() is True


def test_log_send_text_timeout_diagnostics_artifact_capture_is_opt_in(monkeypatch):
    captured = []

    monkeypatch.delenv("GLASS_CAPTURE_TIMEOUT_ARTIFACTS", raising=False)
    monkeypatch.setattr(
        ui_helpers,
        "_dump_artifacts",
        lambda driver, prefix="debug": captured.append((driver, prefix)),
    )

    ui_helpers._log_send_text_timeout_diagnostics(
        _FakeDriver(), ("id", "wwid"), "E96693"
    )

    assert captured == []
