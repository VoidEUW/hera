"""Prompt state: round trip, identity, locks, patches, diff."""

from __future__ import annotations

import pytest

from hera_prompts import (
    ROOT,
    Prompt,
    RendererConfig,
    Role,
    Section,
    SectionError,
    TraitError,
    TraitPatch,
    TraitRegistry,
    TraitValue,
    diff,
)


def test_json_round_trip_keeps_fingerprint(reference_prompt: Prompt) -> None:
    restored = Prompt.model_validate_json(reference_prompt.model_dump_json())
    assert restored == reference_prompt
    assert restored.fingerprint() == reference_prompt.fingerprint()


def test_fingerprint_ignores_trait_insertion_order() -> None:
    """Two prompts built in a different order are the same prompt."""
    forward = Prompt(traits={"a.one": 1, "b.two": 2})
    backward = Prompt(traits={"b.two": 2, "a.one": 1})
    assert forward.fingerprint() == backward.fingerprint()
    assert list(forward.traits) == list(backward.traits) == ["a.one", "b.two"]


def test_locked_traits_cannot_be_mutated_in_place(reference_prompt: Prompt) -> None:
    with pytest.raises(AttributeError):
        reference_prompt.locked_traits.add("behavior.tone")  # type: ignore[attr-defined]


def test_fingerprint_tracks_renderer_config(reference_prompt: Prompt) -> None:
    other = reference_prompt.model_copy(update={"renderer": RendererConfig(format="xml")})
    assert other.fingerprint() != reference_prompt.fingerprint()


def test_paths_and_get(reference_prompt: Prompt) -> None:
    assert reference_prompt.paths() == [
        "identity",
        "behavior",
        "behavior.character",
        "tools",
        "memories",
        "request",
    ]
    section = reference_prompt.get("behavior.character")
    assert section is not None and section.role is Role.DEVELOPER
    assert reference_prompt.get("nope") is None


def test_replace_on_locked_section_returns_unchanged_object(reference_prompt: Prompt) -> None:
    assert reference_prompt.is_locked("identity")
    assert reference_prompt.replace("identity", content="anders") == reference_prompt


def test_replace_updates_a_nested_section(reference_prompt: Prompt) -> None:
    updated = reference_prompt.replace("behavior.character", content="Knapp.", title="Charakter")
    section = updated.get("behavior.character")
    assert section is not None
    assert (section.content, section.title) == ("Knapp.", "Charakter")
    original = reference_prompt.get("behavior.character")
    assert original is not None and original.title is None


def test_remove_on_locked_section_returns_unchanged_object(reference_prompt: Prompt) -> None:
    assert reference_prompt.remove("tools") == reference_prompt


def test_remove_drops_the_subtree(reference_prompt: Prompt) -> None:
    assert "behavior.character" not in reference_prompt.remove("behavior").paths()


def test_insert_below_parent_and_after_sibling(reference_prompt: Prompt) -> None:
    prompt = reference_prompt.insert(
        "behavior", Section(key="behavior.style", content="Kurze Sätze.")
    )
    prompt = prompt.insert(
        "behavior",
        Section(key="behavior.voice", content="Erste Person."),
        after="behavior.character",
    )
    assert prompt.paths()[1:4] == ["behavior", "behavior.character", "behavior.voice"]
    assert prompt.paths()[4] == "behavior.style"


def test_insert_at_root(reference_prompt: Prompt) -> None:
    prompt = reference_prompt.insert(ROOT, Section(key="epilogue", content="Ende."))
    assert prompt.paths()[-1] == "epilogue"


def test_insert_with_wrong_prefix_raises(reference_prompt: Prompt) -> None:
    with pytest.raises(SectionError):
        reference_prompt.insert("behavior", Section(key="style", content="x"))


def test_insert_into_locked_parent_returns_unchanged_object(reference_prompt: Prompt) -> None:
    prompt = reference_prompt.insert("tools", Section(key="tools.extra", content="x"))
    assert prompt == reference_prompt


def test_reorder_roots(reference_prompt: Prompt) -> None:
    order = ["request", "memories", "tools", "behavior", "identity"]
    assert reference_prompt.reorder(ROOT, order).paths()[:2] == ["request", "memories"]


def test_reorder_with_incomplete_order_raises(reference_prompt: Prompt) -> None:
    with pytest.raises(SectionError):
        reference_prompt.reorder(ROOT, ["identity"])


def test_set_enabled(reference_prompt: Prompt) -> None:
    disabled = reference_prompt.set_enabled("behavior", False)
    section = disabled.get("behavior")
    assert section is not None and not section.enabled
    assert reference_prompt.set_enabled("identity", False) == reference_prompt


def test_duplicate_key_across_roots_raises() -> None:
    with pytest.raises(SectionError):
        Prompt(sections=[Section(key="identity"), Section(key="identity")])


def test_invalid_trait_key_raises() -> None:
    with pytest.raises(TraitError):
        Prompt(traits={"Behavior.Tone": "terse"})


def test_replace_without_arguments_returns_unchanged_object(reference_prompt: Prompt) -> None:
    assert reference_prompt.replace("behavior.character") == reference_prompt


def test_transformations_on_unknown_keys_raise(reference_prompt: Prompt) -> None:
    """An unknown key is a caller error and must not pass silently — otherwise a stale
    address yields an unchanged prompt that looks like a successful transformation."""
    with pytest.raises(SectionError):
        reference_prompt.replace("nope", content="x")
    with pytest.raises(SectionError):
        reference_prompt.remove("nope")
    with pytest.raises(SectionError):
        reference_prompt.set_enabled("nope", False)
    with pytest.raises(SectionError):
        reference_prompt.insert("nope", Section(key="nope.child"))
    with pytest.raises(SectionError):
        reference_prompt.reorder("nope", [])


def test_transformations_on_locked_keys_return_unchanged_object(reference_prompt: Prompt) -> None:
    """A locked key is a policy decision and stays silent — the counterpart to the test
    above."""
    assert reference_prompt.replace("identity", content="anders") == reference_prompt
    assert reference_prompt.remove("identity") == reference_prompt
    assert reference_prompt.set_enabled("identity", False) == reference_prompt


def test_insert_at_root_rejects_dotted_key(reference_prompt: Prompt) -> None:
    with pytest.raises(SectionError):
        reference_prompt.insert(ROOT, Section(key="behavior.style"))


def test_insert_after_unknown_sibling_raises(reference_prompt: Prompt) -> None:
    with pytest.raises(SectionError):
        reference_prompt.insert("behavior", Section(key="behavior.style"), after="behavior.missing")


def test_reorder_nested_children(reference_prompt: Prompt) -> None:
    prompt = reference_prompt.insert("behavior", Section(key="behavior.style", content="Kurz."))
    reordered = prompt.reorder("behavior", ["behavior.style", "behavior.character"])
    assert reordered.paths()[1:4] == ["behavior", "behavior.style", "behavior.character"]


def test_reorder_locked_parent_returns_unchanged_object(reference_prompt: Prompt) -> None:
    assert reference_prompt.reorder("tools", []) == reference_prompt


def test_apply_sets_and_deletes_traits(reference_prompt: Prompt) -> None:
    result = reference_prompt.apply(
        TraitPatch(changes={"behavior.tone": "ample", "behavior.hallucinate": None})
    )
    assert result.prompt.traits == {"behavior.tone": "ample"}
    assert result.applied == {"behavior.tone": "ample", "behavior.hallucinate": None}
    assert result.rejected == []


def test_apply_leaves_the_original_untouched(reference_prompt: Prompt) -> None:
    reference_prompt.apply(TraitPatch(changes={"behavior.tone": "ample"}))
    assert reference_prompt.traits["behavior.tone"] == "terse"


def test_apply_rejects_locked_trait_without_raising(reference_prompt: Prompt) -> None:
    locked = reference_prompt.model_copy(update={"locked_traits": {"behavior.tone"}})
    result = locked.apply(TraitPatch(changes={"behavior.tone": "ample"}))
    assert result.prompt == locked
    assert [(r.key, r.reason) for r in result.rejected] == [("behavior.tone", "locked")]
    assert result.applied == {}


def test_apply_rejects_spec_locked_trait(reference_prompt: Prompt) -> None:
    from hera_prompts import TraitSpec

    registry = TraitRegistry(specs=[TraitSpec(key="behavior.tone", type="str", locked=True)])
    result = reference_prompt.apply(
        TraitPatch(changes={"behavior.tone": "ample"}), registry=registry
    )
    assert [r.reason for r in result.rejected] == ["locked"]


def test_apply_rejects_unknown_trait_under_closed_registry(reference_prompt: Prompt) -> None:
    registry = TraitRegistry(allow_unknown=False)
    result = reference_prompt.apply(
        TraitPatch(changes={"behavior.mood": "sunny"}), registry=registry
    )
    assert [(r.key, r.reason) for r in result.rejected] == [("behavior.mood", "unknown_trait")]
    assert result.prompt.traits == reference_prompt.traits


def test_apply_rejects_invalid_value(
    reference_prompt: Prompt, reference_registry: TraitRegistry
) -> None:
    result = reference_prompt.apply(
        TraitPatch(changes={"behavior.tone": "chatty"}), registry=reference_registry
    )
    assert [(r.key, r.reason) for r in result.rejected] == [("behavior.tone", "invalid_value")]


def test_apply_rejects_invalid_key(reference_prompt: Prompt) -> None:
    result = reference_prompt.apply(TraitPatch(changes={"Behavior.Tone": "ample"}))
    assert [r.reason for r in result.rejected] == ["invalid_key"]


def test_apply_is_order_independent(reference_prompt: Prompt) -> None:
    changes: dict[str, TraitValue | None] = {"z.one": "a", "a.two": "b"}
    forward = reference_prompt.apply(TraitPatch(changes=changes)).prompt
    backward = reference_prompt.apply(TraitPatch(changes=dict(reversed(changes.items())))).prompt
    assert forward.fingerprint() == backward.fingerprint()


def test_check_reports_nothing_when_the_prompt_matches_the_registry(
    reference_prompt: Prompt, reference_registry: TraitRegistry
) -> None:
    assert reference_prompt.check(reference_registry) == []


def test_check_finds_values_a_narrowed_spec_no_longer_admits(
    reference_prompt: Prompt,
) -> None:
    """A prompt outlives the specs it was built against."""
    from hera_prompts import TraitSpec

    narrowed = TraitRegistry(
        specs=[TraitSpec(key="behavior.tone", type="str", choices=["ample"])],
        allow_unknown=False,
    )
    assert [(r.key, r.reason) for r in reference_prompt.check(narrowed)] == [
        ("behavior.hallucinate", "unknown_trait"),
        ("behavior.tone", "invalid_value"),
    ]


def test_diff_lists_exactly_the_changed_traits(reference_prompt: Prompt) -> None:
    child = reference_prompt.apply(
        TraitPatch(
            changes={
                "behavior.tone": "ample",
                "behavior.hallucinate": None,
                "formatting.max_words": 40,
            }
        )
    ).prompt
    result = diff(reference_prompt, child)
    assert [(t.key, t.before, t.after) for t in result.traits] == [
        ("behavior.hallucinate", "never", None),
        ("behavior.tone", "terse", "ample"),
        ("formatting.max_words", None, 40),
    ]
    assert result.sections == []
    assert result.renderer == []


def test_diff_reports_sections_and_renderer(reference_prompt: Prompt) -> None:
    other = reference_prompt.replace("behavior.character", content="Anders.")
    other = other.remove("memories").insert(ROOT, Section(key="epilogue", content="Ende."))
    other = other.model_copy(update={"renderer": RendererConfig(format="xml")})
    result = diff(reference_prompt, other)
    assert [(s.key, s.kind, s.fields) for s in result.sections] == [
        ("behavior.character", "modified", ["content"]),
        ("epilogue", "added", []),
        ("memories", "removed", []),
    ]
    assert [(r.field, r.before, r.after) for r in result.renderer] == [
        ("format", "keyvalue", "xml")
    ]
