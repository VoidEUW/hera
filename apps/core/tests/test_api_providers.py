"""Registering endpoints and the named models on them.

The screen a person reaches for first, because nothing else in Hera does anything until she is
pointed at a model. The things worth being strict about: the key never comes back, a change
takes effect without a restart, an old ``model: str`` file still loads, and a model id
containing ``/`` still works everywhere one is accepted.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from core_support import API
from httpx import AsyncClient

from hera_core.config import ConfigError, HeraConfig, ModelEntry, ProviderEntry, load, save
from hera_home import logo_path


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
        assert body["providers"][0]["active_model"]
        assert body["providers"][0]["models"][0]["id"] == body["providers"][0]["active_model"]

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
                "model_id": "qwen3.6-35b",
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
            json={"name": "studio", "base_url": "http://localhost:4891/v1", "model_id": "qwen"},
        )
        assert added.status_code == 201
        assert added.json()["providers"][-1]["active_model"] == "qwen"

        body = (await client.post(f"{API}/providers/studio/activate")).json()
        assert body["active"] == "studio"

    async def test_a_duplicate_name_is_refused(self, client: AsyncClient) -> None:
        payload = {"name": "studio", "base_url": "http://localhost:4891/v1", "model_id": "qwen"}
        assert (await client.post(f"{API}/providers", json=payload)).status_code == 201
        assert (await client.post(f"{API}/providers", json=payload)).status_code == 409

    async def test_a_name_that_would_not_survive_a_url_is_refused(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            f"{API}/providers",
            json={"name": "My Server!", "base_url": "http://x/v1", "model_id": "qwen"},
        )
        assert response.status_code == 422

    async def test_deleting_the_active_one_promotes_another(self, client: AsyncClient) -> None:
        """A person with two endpoints who removes the one they were using must not be left
        with a Hera pointed at nothing."""
        await client.post(
            f"{API}/providers",
            json={"name": "studio", "base_url": "http://localhost:4891/v1", "model_id": "qwen"},
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
        await client.patch(f"{API}/providers/local", json={"embedding_model": "e5"})

        body = (await client.get(f"{API}/providers")).json()
        entry = body["providers"][0]
        assert entry["embedding_model"] == "e5"
        assert entry["base_url"].startswith("http")

    async def test_omitting_the_key_keeps_it(self, client: AsyncClient) -> None:
        """The screen never receives the key, so this is the only way it can preserve one."""
        await client.patch(f"{API}/providers/local", json={"api_key": "sk-kept"})
        await client.patch(f"{API}/providers/local", json={"embedding_model": "e5"})

        assert (await client.get(f"{API}/providers")).json()["providers"][0]["api_key_set"]

    async def test_an_empty_key_clears_it(self, client: AsyncClient) -> None:
        await client.patch(f"{API}/providers/local", json={"api_key": "sk-kept"})
        await client.patch(f"{API}/providers/local", json={"api_key": ""})

        assert not (await client.get(f"{API}/providers")).json()["providers"][0]["api_key_set"]


class TestModels:
    async def test_registering_a_second_model_does_not_change_the_active_one(
        self, client: AsyncClient
    ) -> None:
        before = (await client.get(f"{API}/providers")).json()["providers"][0]["active_model"]

        body = (await client.post(f"{API}/providers/local/models", json={"id": "second"})).json()

        entry = next(p for p in body["providers"] if p["name"] == "local")
        assert {m["id"] for m in entry["models"]} == {before, "second"}
        assert entry["active_model"] == before

    async def test_registering_an_existing_id_replaces_it_rather_than_duplicating(
        self, client: AsyncClient
    ) -> None:
        await client.post(f"{API}/providers/local/models", json={"id": "second", "name": "old"})

        body = (
            await client.post(f"{API}/providers/local/models", json={"id": "second", "name": "new"})
        ).json()

        entry = next(p for p in body["providers"] if p["name"] == "local")
        matching = [m for m in entry["models"] if m["id"] == "second"]
        assert len(matching) == 1
        assert matching[0]["name"] == "new"

    async def test_a_registered_models_name_defaults_to_its_id(self, client: AsyncClient) -> None:
        body = (
            await client.post(f"{API}/providers/local/models", json={"id": "no-name-given"})
        ).json()
        entry = next(p for p in body["providers"] if p["name"] == "local")
        registered = next(m for m in entry["models"] if m["id"] == "no-name-given")
        assert registered["name"] == "no-name-given"

    async def test_the_first_model_registered_on_a_model_less_provider_becomes_active(
        self, client: AsyncClient
    ) -> None:
        await client.post(f"{API}/providers/local/models", json={"id": "only"})
        first = (await client.get(f"{API}/providers")).json()["providers"][0]
        await client.delete(f"{API}/providers/local/models?id={first['active_model']}")

        remaining = (await client.get(f"{API}/providers")).json()["providers"][0]
        assert remaining["active_model"] == "only"

        await client.delete(f"{API}/providers/local/models?id=only")
        empty = (await client.get(f"{API}/providers")).json()["providers"][0]
        assert empty["models"] == []
        assert empty["active_model"] == ""

        body = (await client.post(f"{API}/providers/local/models", json={"id": "revived"})).json()
        assert body["providers"][0]["active_model"] == "revived"

    async def test_removing_the_active_model_promotes_another_remaining_one(
        self, client: AsyncClient
    ) -> None:
        original = (await client.get(f"{API}/providers")).json()["providers"][0]["active_model"]
        await client.post(f"{API}/providers/local/models", json={"id": "second"})

        body = (await client.delete(f"{API}/providers/local/models?id={original}")).json()

        entry = body["providers"][0]
        assert entry["active_model"] == "second"
        assert original not in {m["id"] for m in entry["models"]}

    async def test_removing_the_last_model_leaves_the_provider_model_less(
        self, client: AsyncClient
    ) -> None:
        original = (await client.get(f"{API}/providers")).json()["providers"][0]["active_model"]

        body = (await client.delete(f"{API}/providers/local/models?id={original}")).json()

        entry = body["providers"][0]
        assert entry["models"] == []
        assert entry["active_model"] == ""

    async def test_removing_an_unknown_model_is_a_404(self, client: AsyncClient) -> None:
        response = await client.delete(f"{API}/providers/local/models?id=nope")
        assert response.status_code == 404

    async def test_a_model_id_containing_a_slash_can_be_registered_and_removed(
        self, client: AsyncClient
    ) -> None:
        """Model ids are routinely vendor-prefixed. A path segment cannot match `/`, so the id
        travels as a query parameter instead."""
        slashed = "meta-llama/Llama-3-70b"
        await client.post(f"{API}/providers/local/models", json={"id": slashed})

        removed = await client.delete(
            f"{API}/providers/local/models",
            params={"id": slashed},
        )
        assert removed.status_code == 200
        entry = removed.json()["providers"][0]
        assert slashed not in {m["id"] for m in entry["models"]}

    async def test_activate_with_a_model_switches_both_in_one_call(
        self, client: AsyncClient
    ) -> None:
        await client.post(
            f"{API}/providers",
            json={"name": "studio", "base_url": "http://localhost:4891/v1", "model_id": "a"},
        )
        await client.post(f"{API}/providers/studio/models", json={"id": "b"})

        body = (await client.post(f"{API}/providers/studio/activate", json={"model": "b"})).json()

        assert body["active"] == "studio"
        entry = next(p for p in body["providers"] if p["name"] == "studio")
        assert entry["active_model"] == "b"

    async def test_activate_with_an_unknown_model_is_a_404(self, client: AsyncClient) -> None:
        response = await client.post(f"{API}/providers/local/activate", json={"model": "nope"})
        assert response.status_code == 404

    async def test_activate_with_no_body_still_works(self, client: AsyncClient) -> None:
        response = await client.post(f"{API}/providers/local/activate")
        assert response.status_code == 200
        assert response.json()["active"] == "local"


class TestLogo:
    async def test_uploading_a_custom_logo_is_served_back_with_its_content_type(
        self, client: AsyncClient
    ) -> None:
        raw = base64.b64encode(b"not-really-a-png").decode()
        await client.patch(
            f"{API}/providers/local",
            json={
                "kind": "custom",
                "logo_data_url": f"data:image/png;base64,{raw}",
                "logo_media_type": "image/png",
            },
        )

        response = await client.get(f"{API}/providers/local/logo")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content == b"not-really-a-png"

    async def test_a_non_image_media_type_is_refused(self, client: AsyncClient) -> None:
        raw = base64.b64encode(b"<script>").decode()
        response = await client.patch(
            f"{API}/providers/local",
            json={
                "logo_data_url": f"data:text/html;base64,{raw}",
                "logo_media_type": "text/html",
            },
        )
        assert response.status_code == 422

    async def test_malformed_base64_is_refused_rather_than_500ing(
        self, client: AsyncClient
    ) -> None:
        """`abc` is valid-looking but wrong-length base64 — `binascii.Error` on decode, not a
        clean `ValueError`. Caught in the schema, before anything on disk is touched."""
        response = await client.patch(
            f"{API}/providers/local",
            json={"logo_data_url": "data:image/png;base64,abc", "logo_media_type": "image/png"},
        )
        assert response.status_code == 422

    async def test_malformed_base64_does_not_delete_the_existing_logo(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("HERA_HOME", str(tmp_path))
        raw = base64.b64encode(b"a-logo").decode()
        await client.patch(
            f"{API}/providers/local",
            json={"logo_data_url": f"data:image/png;base64,{raw}", "logo_media_type": "image/png"},
        )

        await client.patch(
            f"{API}/providers/local",
            json={"logo_data_url": "data:image/png;base64,abc", "logo_media_type": "image/png"},
        )

        assert logo_path("local").is_file()
        assert logo_path("local").read_bytes() == b"a-logo"

    async def test_clearing_the_logo_removes_the_file(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("HERA_HOME", str(tmp_path))
        raw = base64.b64encode(b"a-logo").decode()
        await client.patch(
            f"{API}/providers/local",
            json={"logo_data_url": f"data:image/png;base64,{raw}", "logo_media_type": "image/png"},
        )
        assert logo_path("local").is_file()

        await client.patch(f"{API}/providers/local", json={"logo_data_url": ""})

        assert not logo_path("local").is_file()

    async def test_deleting_the_provider_also_deletes_its_logo_file(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("HERA_HOME", str(tmp_path))
        await client.post(
            f"{API}/providers",
            json={"name": "studio", "base_url": "http://localhost:4891/v1", "model_id": "a"},
        )
        raw = base64.b64encode(b"a-logo").decode()
        await client.patch(
            f"{API}/providers/studio",
            json={"logo_data_url": f"data:image/png;base64,{raw}", "logo_media_type": "image/png"},
        )
        assert logo_path("studio").is_file()

        await client.delete(f"{API}/providers/studio")

        assert not logo_path("studio").is_file()

    async def test_a_provider_with_no_logo_uploaded_is_a_404_on_the_logo_route(
        self, client: AsyncClient
    ) -> None:
        response = await client.get(f"{API}/providers/local/logo")
        assert response.status_code == 404


class TestTakingEffect:
    async def test_activating_repoints_the_running_application(
        self, client: AsyncClient, services: object
    ) -> None:
        """Without a restart. Telling somebody to restart the server to find out whether the
        URL was right turns a two-second correction into a minute."""
        await client.post(
            f"{API}/providers",
            json={
                "name": "studio",
                "base_url": "http://localhost:4891/v1",
                "model_id": "big-one",
            },
        )
        await client.post(f"{API}/providers/studio/activate")

        assert (await client.get(f"{API}/health")).json()["model"] == "big-one"

    async def test_the_model_name_travels_with_the_endpoint(self, client: AsyncClient) -> None:
        """They are one decision: pointing a new server at the old model's name fails as an
        unhelpful 404 from somebody else's API."""
        await client.post(f"{API}/providers/local/models", json={"id": "renamed"})
        await client.post(f"{API}/providers/local/activate", json={"model": "renamed"})
        assert (await client.get(f"{API}/health")).json()["model"] == "renamed"

    async def test_removing_the_last_model_clears_the_live_model_too(
        self, client: AsyncClient
    ) -> None:
        """`active_model` going to `""` must reach the running application, not just the file —
        otherwise a later chat request still carries a model id that no longer exists anywhere
        in the registry."""
        original = (await client.get(f"{API}/providers")).json()["providers"][0]["active_model"]

        await client.delete(f"{API}/providers/local/models?id={original}")

        assert (await client.get(f"{API}/health")).json()["model"] == ""

    async def test_an_injected_provider_is_not_closed_by_a_reconfiguration(
        self, client: AsyncClient, services: object
    ) -> None:
        """The test's FakeProvider belongs to the test. Closing something the container did
        not open is how a suite starts failing in whatever order it happens to run in."""
        injected = services.provider  # type: ignore[attr-defined]

        await client.patch(f"{API}/providers/local", json={"embedding_model": "e5"})

        assert injected.closed is False
        assert services.provider is not injected  # type: ignore[attr-defined]


GLM_OPTIONS = {"chat_template_kwargs": {"enable_thinking": True, "clear_thinking": False}}


class TestModelOptions:
    """Issue #63. GLM-4.7 renders a multi-turn history as if it had just started unless it is
    told ``chat_template_kwargs.clear_thinking = false``, and there was nowhere to say so.

    Registered per model rather than per endpoint, because the same OpenRouter URL serves
    GLM-4.7 and GLM5.3 and only one of them wants it.
    """

    async def test_they_are_stored_and_come_back(self, client: AsyncClient) -> None:
        await client.post(
            f"{API}/providers/local/models", json={"id": "glm-4.7-flash", "options": GLM_OPTIONS}
        )

        body = (await client.get(f"{API}/providers")).json()
        model = next(m for m in body["providers"][0]["models"] if m["id"] == "glm-4.7-flash")
        assert model["options"] == GLM_OPTIONS

    async def test_they_reach_the_running_turn_when_the_model_is_activated(
        self, client: AsyncClient, services: object
    ) -> None:
        """The whole point. A flag that is saved and does not apply until a restart is a flag
        somebody will conclude does not work."""
        await client.post(
            f"{API}/providers/local/models", json={"id": "glm-4.7-flash", "options": GLM_OPTIONS}
        )
        await client.post(f"{API}/providers/local/activate", json={"model": "glm-4.7-flash"})

        assert services.orchestrator.settings.extra == GLM_OPTIONS  # type: ignore[attr-defined]

    async def test_switching_to_a_plain_model_takes_them_away_again(
        self, client: AsyncClient, services: object
    ) -> None:
        """They belong to a model, not to an endpoint. Carrying GLM-4.7's flags over to the
        model beside it sends them to a server that has never heard of them."""
        await client.post(
            f"{API}/providers/local/models", json={"id": "glm-4.7-flash", "options": GLM_OPTIONS}
        )
        await client.post(f"{API}/providers/local/activate", json={"model": "glm-4.7-flash"})
        await client.post(f"{API}/providers/local/models", json={"id": "glm5.3"})
        await client.post(f"{API}/providers/local/activate", json={"model": "glm5.3"})

        assert services.orchestrator.settings.extra == {}  # type: ignore[attr-defined]

    async def test_editing_a_registered_model_replaces_its_options(
        self, client: AsyncClient
    ) -> None:
        await client.post(
            f"{API}/providers/local/models", json={"id": "glm-4.7-flash", "options": GLM_OPTIONS}
        )
        await client.post(
            f"{API}/providers/local/models", json={"id": "glm-4.7-flash", "options": {}}
        )

        body = (await client.get(f"{API}/providers")).json()
        model = next(m for m in body["providers"][0]["models"] if m["id"] == "glm-4.7-flash")
        assert model["options"] == {}

    async def test_a_key_that_would_replace_the_conversation_is_refused(
        self, client: AsyncClient
    ) -> None:
        """``extra`` is merged into the body last, so ``messages`` typed in here would empty
        the conversation — and the symptom would be a model that has forgotten everything,
        which is indistinguishable from the bug this field exists to fix."""
        response = await client.post(
            f"{API}/providers/local/models", json={"id": "m", "options": {"messages": []}}
        )

        assert response.status_code == 422
        assert "messages" in response.text

    async def test_they_survive_the_file(self, client: AsyncClient) -> None:
        """It is a nested TOML table, and a person has to be able to read and edit it."""
        await client.post(
            f"{API}/providers/local/models", json={"id": "glm-4.7-flash", "options": GLM_OPTIONS}
        )

        entry = load().get("local")
        assert entry is not None
        assert next(m for m in entry.models if m.id == "glm-4.7-flash").options == GLM_OPTIONS

    async def test_the_known_ones_are_offered(self, client: AsyncClient) -> None:
        """Picked, never guessed from a model id — `glm-4.7-flash` and `zai/glm-4.7` are the
        same weights under two names, and guessing wrong sends a flag to a server that rejects
        the whole request."""
        body = (await client.get(f"{API}/providers")).json()

        glm = next(p for p in body["presets"] if p["id"] == "glm-4.7")
        assert glm["options"] == GLM_OPTIONS
        assert glm["hint"]


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


class TestMigration:
    def test_a_bare_model_field_is_read_as_one_registered_model(self, tmp_path: Path) -> None:
        """Old files said `model: str`. Every load normalizes that into one registered, active
        model — a permanent read-time rule, not a one-off migration script."""
        path = tmp_path / "config.toml"
        path.write_text(
            '[[providers]]\nname = "studio"\nbase_url = "http://x/v1"\nmodel = "qwen"\n'
        )

        entry = load(path).get("studio")

        assert entry is not None
        assert entry.models == [ModelEntry(id="qwen", name="qwen")]
        assert entry.active_model == "qwen"

    def test_a_file_with_both_shapes_present_prefers_the_new_one(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        path.write_text(
            '[[providers]]\nname = "studio"\nbase_url = "http://x/v1"\nmodel = "old"\n'
            'models = [{ id = "new", name = "new" }]\nactive_model = "new"\n'
        )

        entry = load(path).get("studio")

        assert entry is not None
        assert [m.id for m in entry.models] == ["new"]
        assert entry.active_model == "new"

    def test_an_active_model_naming_a_removed_model_falls_back_to_the_first(self) -> None:
        entry = ProviderEntry(
            name="studio", models=[ModelEntry(id="a", name="a")], active_model="gone"
        )
        assert entry.active_model == "a"

    def test_an_active_model_with_no_registered_models_is_cleared(self) -> None:
        entry = ProviderEntry(name="studio", models=[], active_model="stale")
        assert entry.active_model == ""

    def test_a_model_table_with_no_id_is_a_config_error_not_a_key_error(
        self, tmp_path: Path
    ) -> None:
        """A hand-edited file missing the one required field belongs on the same "the parser's
        own complaint" path as any other malformed file, not a 500 from an unwrapped
        `KeyError`."""
        path = tmp_path / "config.toml"
        path.write_text(
            '[[providers]]\nname = "studio"\nbase_url = "http://x/v1"\n'
            'models = [{ name = "qwen" }]\n'
        )

        with pytest.raises(ConfigError):
            load(path)

    def test_an_empty_provider_model_environment_variable_is_a_config_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """`pydantic-settings` does not treat an empty environment value as unset, so
        `HERA_PROVIDER_MODEL=""` reaches `ModelEntry` as an empty id. That should read as a
        wrong deployment, not an unhandled `ValidationError`."""
        monkeypatch.setenv("HERA_PROVIDER_MODEL", "")

        with pytest.raises(ConfigError):
            load(tmp_path / "config.toml")


class TestTheFile:
    def test_it_is_readable_and_editable_by_hand(self, tmp_path: Path) -> None:
        """There must be nothing in ~/.hera you cannot open in an editor."""
        config = load(tmp_path / "config.toml").with_provider(
            ProviderEntry(
                name="studio",
                base_url="http://x/v1",
                models=[ModelEntry(id="qwen", name="qwen")],
                active_model="qwen",
                api_key='a"quote',
            )
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
            load(path)
            .with_provider(
                ProviderEntry(
                    name="studio", models=[ModelEntry(id="q", name="q")], active_model="q"
                )
            )
            .activated("gone"),
            path,
        )
        active = load(path).active()
        assert active is not None and active.name == "local"


class TestWhatIsWrittenDown:
    """`config.toml` should mean *what I decided*, not *what the defaults were the day I
    installed it*.

    The file is seeded from the environment on first run and wins afterwards, which is right.
    What was wrong is that seeding dumped every field including the ones nobody had an opinion
    about — so a default this project later improves was silently dead for anybody who had
    already run Hera. It surfaced as a turn ending in *did not answer in time* against an
    install whose `timeout_s = 180.0` had never been chosen by a person.
    """

    def test_an_untouched_tuning_field_is_left_out(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        save(HeraConfig(providers=[ProviderEntry(name="local")], active_provider="local"), path)

        assert "timeout_s" not in path.read_text(encoding="utf-8")

    def test_a_value_somebody_set_is_written(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        save(
            HeraConfig(providers=[ProviderEntry(name="local", timeout_s=45.0)]),
            path,
        )

        assert "timeout_s = 45.0" in path.read_text(encoding="utf-8")

    def test_a_value_somebody_set_still_wins_on_the_way_back(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        save(HeraConfig(providers=[ProviderEntry(name="local", timeout_s=45.0)]), path)

        assert load(path).providers[0].timeout_s == 45.0

    def test_an_omitted_field_follows_the_default(self, tmp_path: Path) -> None:
        """The property the whole change exists for: improve the default, and an install that
        never expressed an opinion gets the improvement."""
        path = tmp_path / "config.toml"
        save(HeraConfig(providers=[ProviderEntry(name="local")]), path)

        assert load(path).providers[0].timeout_s == ProviderEntry(name="x").timeout_s

    def test_the_endpoint_itself_is_written_even_when_it_is_the_default(
        self, tmp_path: Path
    ) -> None:
        """The rest of an entry is what you came to the file to read. An endpoint with no
        `base_url` in it is a worse file even when the URL is the default one."""
        path = tmp_path / "config.toml"
        save(HeraConfig(providers=[ProviderEntry(name="local")]), path)

        assert "base_url" in path.read_text(encoding="utf-8")

    def test_kind_and_models_are_written_even_when_default(self, tmp_path: Path) -> None:
        path = tmp_path / "config.toml"
        save(
            HeraConfig(
                providers=[
                    ProviderEntry(
                        name="local",
                        models=[ModelEntry(id="qwen", name="qwen")],
                        active_model="qwen",
                    )
                ]
            ),
            path,
        )

        body = path.read_text(encoding="utf-8")
        assert "kind" in body
        assert "models" in body
        assert "active_model" in body
