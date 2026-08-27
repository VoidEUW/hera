"""Registering endpoints.

The screen a person reaches for first, because nothing else in Hera does anything until she is
pointed at a model. The two things worth being strict about: the key never comes back, and a
change takes effect without a restart.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core_support import API
from httpx import AsyncClient

from hera_core.config import ProviderEntry, load, save


class TestReading:
    async def test_a_fresh_install_is_seeded_from_the_environment(
        self, client: AsyncClient
    ) -> None:
        """The defaults describe the intended deployment, so what a person finds is the right
        shape to correct rather than an empty form."""
        body = (await client.get(f"{API}/providers")).json()

        assert [p["name"] for p in body["providers"]] == ["local"]
        assert body["active"] == "local"
        assert body["providers"][0]["base_url"].startswith("http")

    async def test_an_existing_environment_variable_is_what_you_find_filled_in(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HERA_PROVIDER_BASE_URL", "http://192.168.1.9:8080/v1")
        body = (await client.get(f"{API}/providers")).json()
        assert body["providers"][0]["base_url"] == "http://192.168.1.9:8080/v1"

    async def test_the_key_never_comes_back(self, client: AsyncClient) -> None:
        """A masked string is something a person tries to edit and a client tries to send
        back, and both end with a key of asterisks saved to disk."""
        await client.post(
            f"{API}/providers",
            json={
                "name": "cloud",
                "base_url": "https://api.example.com/v1",
                "model": "qwen3.6-35b",
                "api_key": "sk-secret",
            },
        )

        response = await client.get(f"{API}/providers")

        assert "sk-secret" not in response.text
        cloud = next(p for p in response.json()["providers"] if p["name"] == "cloud")
        assert cloud["api_key_set"] is True
        assert "api_key" not in cloud


class TestRegistering:
    async def test_adding_one_and_activating_it(self, client: AsyncClient) -> None:
        added = await client.post(
            f"{API}/providers",
            json={"name": "studio", "base_url": "http://localhost:4891/v1", "model": "qwen"},
        )
        assert added.status_code == 201

        body = (await client.post(f"{API}/providers/studio/activate")).json()
        assert body["active"] == "studio"

    async def test_a_duplicate_name_is_refused(self, client: AsyncClient) -> None:
        payload = {"name": "studio", "base_url": "http://localhost:4891/v1", "model": "qwen"}
        assert (await client.post(f"{API}/providers", json=payload)).status_code == 201
        assert (await client.post(f"{API}/providers", json=payload)).status_code == 409

    async def test_a_name_that_would_not_survive_a_url_is_refused(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            f"{API}/providers",
            json={"name": "My Server!", "base_url": "http://x/v1", "model": "qwen"},
        )
        assert response.status_code == 422

    async def test_deleting_the_active_one_promotes_another(self, client: AsyncClient) -> None:
        """A person with two endpoints who removes the one they were using must not be left
        with a Hera pointed at nothing."""
        await client.post(
            f"{API}/providers",
            json={"name": "studio", "base_url": "http://localhost:4891/v1", "model": "qwen"},
        )
        await client.post(f"{API}/providers/studio/activate")

        body = (await client.delete(f"{API}/providers/studio")).json()

        assert body["active"] == "local"

    async def test_an_unknown_provider_is_a_404(self, client: AsyncClient) -> None:
        assert (await client.post(f"{API}/providers/nope/activate")).status_code == 404
        assert (await client.delete(f"{API}/providers/nope")).status_code == 404
        assert (await client.get(f"{API}/providers/nope/models")).status_code == 404


class TestPatching:
    async def test_a_field_left_out_is_left_alone(self, client: AsyncClient) -> None:
        await client.patch(f"{API}/providers/local", json={"model": "qwen3.6-35b-instruct"})

        body = (await client.get(f"{API}/providers")).json()
        entry = body["providers"][0]
        assert entry["model"] == "qwen3.6-35b-instruct"
        assert entry["base_url"].startswith("http")

    async def test_omitting_the_key_keeps_it(self, client: AsyncClient) -> None:
        """The screen never receives the key, so this is the only way it can preserve one."""
        await client.patch(f"{API}/providers/local", json={"api_key": "sk-kept"})
        await client.patch(f"{API}/providers/local", json={"model": "something-else"})

        assert (await client.get(f"{API}/providers")).json()["providers"][0]["api_key_set"]

    async def test_an_empty_key_clears_it(self, client: AsyncClient) -> None:
        await client.patch(f"{API}/providers/local", json={"api_key": "sk-kept"})
        await client.patch(f"{API}/providers/local", json={"api_key": ""})

        assert not (await client.get(f"{API}/providers")).json()["providers"][0]["api_key_set"]


class TestTakingEffect:
    async def test_activating_repoints_the_running_application(
        self, client: AsyncClient, services: object
    ) -> None:
        """Without a restart. Telling somebody to restart the server to find out whether the
        URL was right turns a two-second correction into a minute."""
        await client.post(
            f"{API}/providers",
            json={"name": "studio", "base_url": "http://localhost:4891/v1", "model": "big-one"},
        )
        await client.post(f"{API}/providers/studio/activate")

        assert (await client.get(f"{API}/health")).json()["model"] == "big-one"

    async def test_the_model_name_travels_with_the_endpoint(self, client: AsyncClient) -> None:
        """They are one decision: pointing a new server at the old model's name fails as an
        unhelpful 404 from somebody else's API."""
        await client.patch(f"{API}/providers/local", json={"model": "renamed"})
        assert (await client.get(f"{API}/health")).json()["model"] == "renamed"

    async def test_an_injected_provider_is_not_closed_by_a_reconfiguration(
        self, client: AsyncClient, services: object
    ) -> None:
        """The test's FakeProvider belongs to the test. Closing something the container did
        not open is how a suite starts failing in whatever order it happens to run in."""
        injected = services.provider  # type: ignore[attr-defined]

        await client.patch(f"{API}/providers/local", json={"model": "renamed"})

        assert injected.closed is False
        assert services.provider is not injected  # type: ignore[attr-defined]


class TestProbing:
    async def test_an_unreachable_endpoint_answers_rather_than_erroring(
        self, client: AsyncClient
    ) -> None:
        """ "Nothing is listening on that port" is the commonest thing to be wrong on a fresh
        install, and it belongs on the screen you were already looking at."""
        await client.patch(f"{API}/providers/local", json={"base_url": "http://127.0.0.1:1/v1"})

        response = await client.get(f"{API}/providers/local/models")

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is False
        assert body["models"] == []
        assert body["error"]


class TestTheFile:
    def test_it_is_readable_and_editable_by_hand(self, tmp_path: Path) -> None:
        """There must be nothing in ~/.hera you cannot open in an editor."""
        config = load(tmp_path / "config.toml").with_provider(
            ProviderEntry(name="studio", base_url="http://x/v1", model="qwen", api_key='a"quote')
        )
        save(config, tmp_path / "config.toml")

        text = (tmp_path / "config.toml").read_text()
        assert "[[providers]]" in text
        assert "safe to edit by hand" in text
        # A quote in a key is exactly what hand-rolled TOML writing gets wrong.
        assert load(tmp_path / "config.toml").get("studio").api_key == 'a"quote'  # type: ignore[union-attr]

    def test_a_broken_file_says_so_rather_than_falling_back(self, tmp_path: Path) -> None:
        """A default quietly taking its place would hide the typo."""
        from hera_core.config import ConfigError

        (tmp_path / "config.toml").write_text("this is not = = toml")
        with pytest.raises(ConfigError):
            load(tmp_path / "config.toml")

    def test_an_active_name_that_no_longer_exists_falls_back_to_the_first(
        self, tmp_path: Path
    ) -> None:
        """Deleting an entry by hand must not leave a working install with no model."""
        path = tmp_path / "config.toml"
        save(
            load(path).with_provider(ProviderEntry(name="studio", model="q")).activated("gone"),
            path,
        )
        active = load(path).active()
        assert active is not None and active.name == "local"
