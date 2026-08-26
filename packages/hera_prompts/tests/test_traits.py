"""Registry behaviour: types, choices, unknown traits, fingerprints."""

from __future__ import annotations

import pytest
from hera_prompts.traits import format_value

from hera_prompts import TraitError, TraitRegistry, TraitSpec


def test_open_registry_admits_unknown_traits() -> None:
    TraitRegistry().validate_value("behavior.mood", "sunny")


def test_closed_registry_rejects_unknown_traits() -> None:
    registry = TraitRegistry(allow_unknown=False)
    with pytest.raises(TraitError):
        registry.validate_value("behavior.mood", "sunny")


def test_bool_and_int_are_told_apart() -> None:
    registry = TraitRegistry(specs=[TraitSpec(key="formatting.max_words", type="int")])
    registry.validate_value("formatting.max_words", 40)
    with pytest.raises(TraitError):
        registry.validate_value("formatting.max_words", True)


def test_bool_traits_render_as_true_and_false() -> None:
    registry = TraitRegistry(specs=[TraitSpec(key="formatting.markdown", type="bool")])
    registry.validate_value("formatting.markdown", False)
    assert format_value(True) == "true"
    assert format_value(False) == "false"


def test_value_outside_choices_raises() -> None:
    registry = TraitRegistry(
        specs=[TraitSpec(key="behavior.tone", type="str", choices=["terse", "ample"])]
    )
    with pytest.raises(TraitError):
        registry.validate_value("behavior.tone", "chatty")


def test_duplicate_spec_raises() -> None:
    with pytest.raises(TraitError):
        TraitRegistry(
            specs=[TraitSpec(key="behavior.tone", type="str")] * 2,
        )


def test_default_must_match_declared_type() -> None:
    with pytest.raises(TraitError):
        TraitSpec(key="behavior.tone", type="str", default=3)


def test_fingerprint_tracks_spec_order(reference_registry: TraitRegistry) -> None:
    """Declaration order decides the order traits render in, so it is part of the
    identity — otherwise the snapshot could not tell two renderings apart."""
    shuffled = TraitRegistry(specs=list(reversed(reference_registry.specs)))
    assert shuffled.fingerprint() != reference_registry.fingerprint()


def test_defaults_are_offered_not_applied(reference_registry: TraitRegistry) -> None:
    registry = TraitRegistry(
        specs=[
            TraitSpec(key="behavior.tone", type="str", default="terse"),
            TraitSpec(key="behavior.hallucinate", type="str"),
        ]
    )
    assert registry.defaults() == {"behavior.tone": "terse"}
    assert reference_registry.defaults() == {}


def test_fingerprint_tracks_allow_unknown(reference_registry: TraitRegistry) -> None:
    closed = TraitRegistry(specs=reference_registry.specs, allow_unknown=False)
    assert closed.fingerprint() != reference_registry.fingerprint()


def test_rendered_sentence_from_mapping(reference_registry: TraitRegistry) -> None:
    spec = reference_registry.get("behavior.tone")
    assert spec is not None
    assert spec.rendered_sentence("terse") == "Antworte knapp. Kein Vorspann, kein Nachklang."
    assert spec.rendered_sentence("ample") is None


def test_rendered_sentence_from_template() -> None:
    spec = TraitSpec(key="formatting.max_words", type="int", render="Bleib unter {value} Wörtern.")
    assert spec.rendered_sentence(40) == "Bleib unter 40 Wörtern."


def test_rendered_sentence_without_template_is_none() -> None:
    assert TraitSpec(key="behavior.tone", type="str").rendered_sentence("terse") is None
