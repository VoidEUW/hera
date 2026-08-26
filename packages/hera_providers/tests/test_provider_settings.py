"""Boot settings, and the two timeouts that are deliberately different."""

from __future__ import annotations

import pytest

from hera_providers import ProviderSettings


def test_the_defaults_describe_a_local_server_with_no_authentication() -> None:
    settings = ProviderSettings()

    assert settings.base_url.startswith("http://localhost")
    assert settings.api_key == ""


def test_embeddings_are_off_until_a_model_is_named() -> None:
    """Empty is not a broken configuration; it means retrieval falls back to keyword overlap."""
    assert ProviderSettings().embedding_model == ""


def test_connecting_gives_up_long_before_reading_does() -> None:
    """An endpoint with nothing listening should be reported at once, not after the read
    timeout. A cold 35B model, meanwhile, is worth waiting for rather than failing the turn."""
    settings = ProviderSettings()

    assert settings.connect_timeout_s < settings.timeout_s


def test_settings_are_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERA_PROVIDER_BASE_URL", "http://mini.local:8000/v1")
    monkeypatch.setenv("HERA_PROVIDER_MODEL", "qwen3.8-35b")

    settings = ProviderSettings()

    assert settings.base_url == "http://mini.local:8000/v1"
    assert settings.model == "qwen3.8-35b"
