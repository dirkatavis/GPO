import config.config_loader as config_loader


def test_get_config_supports_dotted_keys(monkeypatch):
    monkeypatch.setattr(
        config_loader,
        "_CONFIG",
        {
            "credentials": {"sso_email": "xe96693@co.abg.com"},
            "delay_seconds": 9,
        },
    )

    assert config_loader.get_config("credentials.sso_email") == "xe96693@co.abg.com"


def test_get_config_returns_default_for_missing_dotted_key(monkeypatch):
    monkeypatch.setattr(config_loader, "_CONFIG", {"credentials": {}})

    assert config_loader.get_config("credentials.missing", "fallback") == "fallback"


def test_merge_dicts_preserves_base_nested_values():
    merged = config_loader._merge_dicts(
        {
            "credentials": {
                "sso_email": "base@company.com",
                "tenant": "base-tenant",
            },
            "delay_seconds": 9,
        },
        {
            "credentials": {"sso_email": "local@company.com"},
        },
    )

    assert merged["credentials"]["sso_email"] == "local@company.com"
    assert merged["credentials"]["tenant"] == "base-tenant"
    assert merged["delay_seconds"] == 9