"""Verify pm_opcode is present in config."""
from config.config_loader import get_config


def test_pm_opcode_returns_pm_gas():
    assert get_config("pm_opcode") == "PM Gas"


def test_pm_opcode_has_comment():
    """Config comment key exists (documents the setting)."""
    import json
    from pathlib import Path
    cfg = json.loads((Path("config/config.json")).read_text(encoding="utf-8"))
    assert "pm_opcode_comment" in cfg
