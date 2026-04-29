"""
Unit tests for playwright_prototype.config.resolve_headless()

Verifies the three-tier precedence:
  1. PLAYWRIGHT_HEADLESS env var  (highest)
  2. 'headless' key in orchestrator_config.json
  3. Default True                 (lowest)

No browser or Playwright installation required.
"""

import json
import pytest

from playwright_prototype.config import resolve_headless


class TestResolveHeadlessEnvVar:
    """Env var takes priority over everything else."""

    def test_env_zero_returns_false(self, monkeypatch):
        monkeypatch.setenv("PLAYWRIGHT_HEADLESS", "0")
        assert resolve_headless() is False

    def test_env_false_returns_false(self, monkeypatch):
        monkeypatch.setenv("PLAYWRIGHT_HEADLESS", "false")
        assert resolve_headless() is False

    def test_env_no_returns_false(self, monkeypatch):
        monkeypatch.setenv("PLAYWRIGHT_HEADLESS", "NO")
        assert resolve_headless() is False

    def test_env_one_returns_true(self, monkeypatch):
        monkeypatch.setenv("PLAYWRIGHT_HEADLESS", "1")
        assert resolve_headless() is True

    def test_env_true_returns_true(self, monkeypatch):
        monkeypatch.setenv("PLAYWRIGHT_HEADLESS", "true")
        assert resolve_headless() is True


class TestResolveHeadlessConfigFile:
    """When env var is absent, reads from the config file passed as config_path."""

    def test_config_false_returns_false(self, monkeypatch, tmp_path):
        monkeypatch.delenv("PLAYWRIGHT_HEADLESS", raising=False)
        cfg = tmp_path / "orchestrator_config.json"
        cfg.write_text(json.dumps({"headless": False}), encoding="utf-8")
        assert resolve_headless(config_path=cfg) is False

    def test_config_true_returns_true(self, monkeypatch, tmp_path):
        monkeypatch.delenv("PLAYWRIGHT_HEADLESS", raising=False)
        cfg = tmp_path / "orchestrator_config.json"
        cfg.write_text(json.dumps({"headless": True}), encoding="utf-8")
        assert resolve_headless(config_path=cfg) is True

    def test_env_overrides_config(self, monkeypatch, tmp_path):
        """Env var wins even when config file says the opposite."""
        monkeypatch.setenv("PLAYWRIGHT_HEADLESS", "0")
        cfg = tmp_path / "orchestrator_config.json"
        cfg.write_text(json.dumps({"headless": True}), encoding="utf-8")
        assert resolve_headless(config_path=cfg) is False


class TestResolveHeadlessDefaults:
    """Falls back to True when neither env var nor config key is present."""

    def test_missing_key_defaults_true(self, monkeypatch, tmp_path):
        monkeypatch.delenv("PLAYWRIGHT_HEADLESS", raising=False)
        cfg = tmp_path / "orchestrator_config.json"
        cfg.write_text(json.dumps({"other_key": "value"}), encoding="utf-8")
        assert resolve_headless(config_path=cfg) is True

    def test_missing_file_defaults_true(self, monkeypatch, tmp_path):
        monkeypatch.delenv("PLAYWRIGHT_HEADLESS", raising=False)
        nonexistent = tmp_path / "nonexistent.json"
        assert resolve_headless(config_path=nonexistent) is True

    def test_invalid_json_defaults_true(self, monkeypatch, tmp_path):
        monkeypatch.delenv("PLAYWRIGHT_HEADLESS", raising=False)
        cfg = tmp_path / "orchestrator_config.json"
        cfg.write_text("not valid json {{", encoding="utf-8")
        assert resolve_headless(config_path=cfg) is True
