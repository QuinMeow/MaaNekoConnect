import json

import pytest

from agent import ad_settings


def settings(**changes):
    return {"version": 1, "enabled": True, "endpoint": ad_settings.ENDPOINT,
            "model": ad_settings.MODEL, "protected_key": "encrypted-test-only"} | changes


def test_no_settings_or_disabled_never_decrypts_or_uses_environment(tmp_path, monkeypatch):
    path = tmp_path / "ad_ai.dat"
    monkeypatch.setenv("MAANEKO_AD_LLM_ENABLED", "1")
    monkeypatch.setattr(ad_settings, "unprotect", lambda _: pytest.fail("Unexpected key access"))
    assert ad_settings.load_config(path) is None
    path.write_text(json.dumps(settings(enabled=False)), encoding="utf-8")
    assert ad_settings.load_config(path) is None


def test_saved_settings_supply_only_in_memory_credentials(tmp_path, monkeypatch):
    path = tmp_path / "ad_ai.dat"
    path.write_text(json.dumps(settings()), encoding="utf-8")
    monkeypatch.setattr(ad_settings, "unprotect", lambda blob: "test-secret" if blob == "encrypted-test-only" else "")
    result = ad_settings.load_config(path)
    assert result == {"endpoint": ad_settings.ENDPOINT, "model": ad_settings.MODEL, "api_key": "test-secret"}
    assert "test-secret" not in path.read_text("utf-8")


@pytest.mark.parametrize("change", [
    {"enabled": "true"}, {"version": 2}, {"protected_key": ""}, {"model": ""},
    {"endpoint": "http://api.deepseek.com/chat/completions"},
    {"endpoint": "https://api.deepseek.com.other.test/chat/completions"},
    {"endpoint": "https://u:p@api.deepseek.com/chat/completions"},
    {"endpoint": "https://api.deepseek.com/chat/completions?key=secret"},
    {"endpoint": "https://api.deepseek.com:444/chat/completions"}, {"api_key": "plaintext"},
])
def test_invalid_or_foreign_settings_fail_before_decrypting(tmp_path, monkeypatch, change):
    path = tmp_path / "ad_ai.dat"
    path.write_text(json.dumps(settings(**change)), encoding="utf-8")
    monkeypatch.setattr(ad_settings, "unprotect", lambda _: pytest.fail("Unexpected key access"))
    with pytest.raises(ValueError):
        ad_settings.load_config(path)


def test_corrupt_and_oversized_settings_fail_closed(tmp_path):
    path = tmp_path / "ad_ai.dat"
    for text in ("{broken", "x" * 32769):
        path.write_text(text, encoding="utf-8")
        with pytest.raises(ValueError):
            ad_settings.load_config(path)


def test_unreadable_credential_is_not_a_fallback_to_environment(tmp_path, monkeypatch):
    path = tmp_path / "ad_ai.dat"
    path.write_text(json.dumps(settings()), encoding="utf-8")
    monkeypatch.setenv("MAANEKO_AD_LLM_API_KEY", "must-not-use")
    monkeypatch.setattr(ad_settings, "unprotect", lambda _: "")
    with pytest.raises(ValueError):
        ad_settings.load_config(path)
