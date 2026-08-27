"""Mind plus profile, compiled into a prompt.

The assertions that matter here are the negative ones: what does *not* end up in the prompt.
An empty section, a slot nobody filled, a trait a profile is no longer allowed to set — each
of those renders as a sentence to the model if it leaks through, and none of them raises.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from hera_profiles import (
    BEHAVIOUR_TRAITS,
    DEPTH,
    EMOJI,
    FORMALITY,
    LANGUAGE,
    SLOT_PROJECT,
    SLOT_SKILLS,
    SLOT_TOOLS,
    MindRepository,
    Profile,
    PromptBuilder,
)


def profile(**fields: object) -> Profile:
    """A detached profile. Nothing here needs it to be persisted."""
    defaults: dict[str, object] = {"owner_id": uuid4(), "slug": "test", "name": "Test"}
    return Profile(**{**defaults, **fields})


def rendered(builder: PromptBuilder, **bindings: str) -> str:
    result = builder.build().render(bindings=bindings, registry=BEHAVIOUR_TRAITS)
    return "\n".join(message.content for message in result.messages)


class TestShape:
    def test_the_regions_land_where_the_layout_says(self, builder: PromptBuilder) -> None:
        keys = builder.build().paths()
        assert "identity.character" in keys
        assert "conduct.safety" in keys
        assert "developer" in keys

    def test_the_developer_message_is_its_own_role(self, builder: PromptBuilder) -> None:
        section = builder.build().get("developer")
        assert section is not None
        assert section.role == "developer"

    def test_identity_and_conduct_are_required(self, builder: PromptBuilder) -> None:
        """Required means never dropped under budget pressure. Her conduct is not something
        that gives way when the context window fills up."""
        prompt = builder.build()
        for key in ("identity", "identity.about_you", "conduct", "conduct.safety", "developer"):
            section = prompt.get(key)
            assert section is not None and section.required, key

    def test_the_xml_rendering_carries_the_address_in_the_tag(self, builder: PromptBuilder) -> None:
        assert "<identity:character>" in rendered(builder)

    def test_two_builds_of_the_same_mind_are_identical(self, builder: PromptBuilder) -> None:
        assert builder.build().fingerprint() == builder.build().fingerprint()

    def test_editing_a_region_changes_the_fingerprint(
        self, builder: PromptBuilder, mind: MindRepository
    ) -> None:
        """Nothing is cached, because the settings screen expects the next turn to differ."""
        before = builder.build().fingerprint()
        mind.write("character", "Someone else entirely.")
        assert builder.build().fingerprint() != before


class TestEmptyRegions:
    def test_an_empty_region_is_left_out_rather_than_rendered_empty(
        self, builder: PromptBuilder, mind: MindRepository
    ) -> None:
        """`<identity:tone></identity:tone>` is a sentence to the model saying "this exists
        and has nothing in it"."""
        mind.write("tone", "")
        prompt = builder.build()
        assert prompt.get("identity.tone") is None
        assert "identity:tone" not in rendered(builder)

    def test_a_group_whose_children_all_vanished_vanishes_too(
        self, builder: PromptBuilder, mind: MindRepository
    ) -> None:
        mind.write("emotion_vocab", "")
        mind.write("emotion_usage", "")
        assert builder.build().get("emotions") is None

    def test_user_prefs_starts_empty_and_is_therefore_absent(self, builder: PromptBuilder) -> None:
        assert builder.build().get("context.user") is None


class TestSlots:
    def test_an_unbound_slot_renders_as_nothing(self, builder: PromptBuilder) -> None:
        """A Hera with no MCP servers must not tell the model about an empty tool list."""
        assert "tools:available" not in rendered(builder)

    def test_a_bound_slot_renders_its_text(self, builder: PromptBuilder) -> None:
        text = rendered(builder, **{SLOT_TOOLS: "fs__read_file — reads a file"})
        assert "fs__read_file" in text
        assert "<tools:available>" in text

    def test_every_declared_slot_is_bindable(self, builder: PromptBuilder) -> None:
        result = builder.build().render(
            bindings={SLOT_TOOLS: "t", SLOT_SKILLS: "s", SLOT_PROJECT: "p", "memories": "m"},
            registry=BEHAVIOUR_TRAITS,
        )
        assert result.unused_bindings == []

    def test_a_slot_nobody_bound_is_reported_rather_than_hidden(
        self, builder: PromptBuilder
    ) -> None:
        result = builder.build().render(registry=BEHAVIOUR_TRAITS)
        assert SLOT_TOOLS in result.snapshot.unbound_slots


class TestProfiles:
    def test_no_profile_builds_the_bare_mind(self, builder: PromptBuilder) -> None:
        assert builder.build().get("identity.character") is not None

    def test_a_disabled_region_is_left_out(self, builder: PromptBuilder) -> None:
        prompt = builder.build(profile(disabled_regions=["emotion_usage"]))
        assert prompt.get("emotions.usage") is None
        assert prompt.get("emotions.vocabulary") is not None

    def test_an_override_replaces_the_file_without_touching_it(
        self, builder: PromptBuilder, mind: MindRepository
    ) -> None:
        prompt = builder.build(profile(overrides={"approach": "Write the test first."}))

        section = prompt.get("approach")
        assert section is not None and section.content is not None
        assert "Write the test first." in section.content
        assert "Write the test first." not in mind.read("approach")

    def test_an_override_does_not_leak_into_another_profile(self, builder: PromptBuilder) -> None:
        """One copy of her character on disk; a profile is a diff against it."""
        builder.build(profile(overrides={"approach": "Something else."}))
        assert "Something else." not in rendered(builder)

    def test_the_renderer_format_comes_from_the_profile(self, builder: PromptBuilder) -> None:
        prompt = builder.build(profile(renderer_format="markdown"))
        assert prompt.renderer.format == "markdown"

    def test_an_unusable_renderer_format_is_rejected_loudly(self, builder: PromptBuilder) -> None:
        with pytest.raises(ValueError, match="format"):
            builder.build(profile(renderer_format="yaml"))

    def test_texts_shows_what_a_profile_will_say(self, builder: PromptBuilder) -> None:
        texts = builder.texts(profile(disabled_regions=["tone"], overrides={"role": "Reviewer."}))
        assert texts["tone"] == ""
        assert texts["role"] == "Reviewer."


class TestTraits:
    def test_the_declared_defaults_are_materialised(self, builder: PromptBuilder) -> None:
        """Not applied during rendering by hera_prompts on purpose -- so the builder is the
        layer that has to put them into the object."""
        assert builder.build().traits[LANGUAGE] == "English"

    def test_a_profile_overrides_a_default(self, builder: PromptBuilder) -> None:
        prompt = builder.build(profile(traits={FORMALITY: "formal"}))
        assert prompt.traits[FORMALITY] == "formal"

    def test_a_trait_renders_as_its_sentence_inside_its_own_section(
        self, builder: PromptBuilder, mind: MindRepository
    ) -> None:
        prompt = builder.build(profile(traits={DEPTH: "brief"}))
        text = "\n".join(
            message.content for message in prompt.render(registry=BEHAVIOUR_TRAITS).messages
        )
        assert "as few words" in text
        assert "<approach:constraints>" in text

    def test_a_value_the_registry_does_not_admit_is_dropped(self, builder: PromptBuilder) -> None:
        prompt = builder.build(profile(traits={FORMALITY: "brusque"}))
        assert prompt.traits[FORMALITY] == "neutral"

    def test_an_undeclared_trait_is_dropped(self, builder: PromptBuilder) -> None:
        """allow_unknown=False: a stray key would otherwise render as a loose line in the
        system prompt, and a region is the place to say something the registry did not
        anticipate."""
        prompt = builder.build(profile(traits={"identity.vibe": "cosy"}))
        assert "identity.vibe" not in prompt.traits

    def test_a_boolean_trait_renders_its_mapped_sentence(self, builder: PromptBuilder) -> None:
        prompt = builder.build(profile(traits={EMOJI: True}))
        text = "\n".join(
            message.content for message in prompt.render(registry=BEHAVIOUR_TRAITS).messages
        )
        assert "Emoji are welcome" in text

    def test_rejected_traits_are_reportable_for_a_settings_screen(
        self, builder: PromptBuilder
    ) -> None:
        """Dropping silently is right at run time and useless in an editor."""
        rejected = builder.rejected_traits(profile(traits={FORMALITY: "brusque"}))
        assert [(item.key, item.reason) for item in rejected] == [(FORMALITY, "invalid_value")]

    def test_a_profile_with_no_traits_has_nothing_to_report(self, builder: PromptBuilder) -> None:
        assert builder.rejected_traits(profile()) == []

    def test_every_trait_prefix_names_a_real_section(self, builder: PromptBuilder) -> None:
        """A trait whose prefix matches no section still renders -- in a general block at the
        top, detached from what it is about. That is the failure mode to watch for."""
        keys = set(builder.build().paths())
        for spec in BEHAVIOUR_TRAITS.specs:
            prefix = spec.key.rsplit(".", 1)[0]
            assert prefix in keys, f"{spec.key} would render in the general block"


class TestForeignContent:
    def test_a_slot_is_not_escaped(self, builder: PromptBuilder) -> None:
        """A skill body or a project's instructions routinely contain code. Escaping would
        hand the model `if count &lt; limit` and expect it to learn from the sample."""
        text = rendered(builder, **{SLOT_SKILLS: "if count < limit && ready"})
        assert "if count < limit && ready" in text

    def test_a_region_is_escaped(self, builder: PromptBuilder, mind: MindRepository) -> None:
        """Text this package authors keeps the default: a region that accidentally contains
        `</identity>` must not appear to close its own element."""
        mind.write("tone", "Never write </identity> in an answer.")
        assert "&lt;/identity&gt;" in rendered(builder)
