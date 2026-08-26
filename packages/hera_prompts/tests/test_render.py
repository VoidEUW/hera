"""Rendering: the reference example, slots, routing, budget and escaping."""

from __future__ import annotations

from xml.etree import ElementTree

import pytest

from hera_prompts import (
    BudgetExceeded,
    MissingBinding,
    Prompt,
    RendererConfig,
    Role,
    Section,
    TokenBudget,
    TraitError,
    TraitPatch,
    TraitRegistry,
    TraitSpec,
)

REFERENCE_SYSTEM = """#IDENTITY
Du bist Hera, eine aufmerksame Assistentin mit eigenem Kopf.

#BEHAVIOR
BEHAVIOR tone = terse
BEHAVIOR hallucinate = never
Du hast eine Meinung und sagst sie. Bei Unsicherheit sagst du das.

#TOOLS
CALL search(query=~~QUERY~~)"""

REFERENCE_USER = """#MEMORIES
MEMORY city = Chemnitz

#REQUEST
Wie war das nochmal mit der Ablation?"""

REFERENCE_BEHAVIOR_XML = """<behavior>
  <behavior:constraints>
    Antworte knapp. Kein Vorspann, kein Nachklang.
    Erfinde nichts. Wenn du etwas nicht weißt, sag es.
  </behavior:constraints>
  <behavior:character>
    Du hast eine Meinung und sagst sie. Bei Unsicherheit sagst du das.
  </behavior:character>
</behavior>"""


REFERENCE_SYSTEM_ADDRESSED = """#IDENTITY
Du bist Hera, eine aufmerksame Assistentin mit eigenem Kopf.

#BEHAVIOR
BEHAVIOR tone = terse
BEHAVIOR hallucinate = never

#BEHAVIOR.CHARACTER
Du hast eine Meinung und sagst sie. Bei Unsicherheit sagst du das.

#TOOLS
CALL search(query=~~QUERY~~)"""


def test_reference_example_keyvalue(
    reference_prompt: Prompt,
    reference_registry: TraitRegistry,
    reference_bindings: dict[str, str],
) -> None:
    """The shape CLAUDE.md pins, reachable through ``nested_headers=False``."""
    prompt = reference_prompt.model_copy(update={"renderer": RendererConfig(nested_headers=False)})
    result = prompt.render(bindings=reference_bindings, registry=reference_registry)
    assert [message.role for message in result.messages] == [Role.SYSTEM, Role.USER]
    assert result.messages[0].content == REFERENCE_SYSTEM
    assert result.messages[1].content == REFERENCE_USER


def test_reference_example_keyvalue_under_the_default(
    reference_prompt: Prompt,
    reference_registry: TraitRegistry,
    reference_bindings: dict[str, str],
) -> None:
    """The same object as it renders out of the box: one extra header, so
    ``behavior.character`` keeps the key that xml and markdown give it too."""
    result = reference_prompt.render(bindings=reference_bindings, registry=reference_registry)
    assert result.messages[0].content == REFERENCE_SYSTEM_ADDRESSED
    assert result.messages[1].content == REFERENCE_USER


def test_reference_example_xml(
    reference_prompt: Prompt,
    reference_registry: TraitRegistry,
    reference_bindings: dict[str, str],
) -> None:
    prompt = reference_prompt.model_copy(update={"renderer": RendererConfig(format="xml")})
    system = prompt.render(bindings=reference_bindings, registry=reference_registry).messages[0]
    start = system.content.index("<behavior>")
    end = system.content.index("</behavior>") + len("</behavior>")
    assert system.content[start:end] == REFERENCE_BEHAVIOR_XML


def test_rendering_twice_is_byte_identical(
    reference_prompt: Prompt,
    reference_registry: TraitRegistry,
    reference_bindings: dict[str, str],
) -> None:
    first = reference_prompt.render(bindings=reference_bindings, registry=reference_registry)
    second = reference_prompt.render(bindings=reference_bindings, registry=reference_registry)
    assert first.messages == second.messages
    assert first.snapshot.content_hash == second.snapshot.content_hash


def test_keyvalue_ignores_the_template_that_xml_uses(
    reference_prompt: Prompt,
    reference_registry: TraitRegistry,
    reference_bindings: dict[str, str],
) -> None:
    keyvalue = reference_prompt.render(
        bindings=reference_bindings, registry=reference_registry
    ).messages[0]
    xml = (
        reference_prompt.model_copy(update={"renderer": RendererConfig(format="xml")})
        .render(bindings=reference_bindings, registry=reference_registry)
        .messages[0]
    )
    assert "BEHAVIOR tone = terse" in keyvalue.content
    assert "Antworte knapp." not in keyvalue.content
    assert "Antworte knapp. Kein Vorspann, kein Nachklang." in xml.content
    assert "BEHAVIOR tone = terse" not in xml.content


def test_trait_without_template_falls_back_to_the_pair(
    reference_prompt: Prompt, reference_bindings: dict[str, str]
) -> None:
    """Inside ``<behavior>`` the group would only repeat the tag."""
    prompt = reference_prompt.model_copy(update={"renderer": RendererConfig(format="xml")})
    content = prompt.render(bindings=reference_bindings).messages[0].content
    assert "<behavior:constraints>\n    hallucinate = never\n    tone = terse" in content
    assert "BEHAVIOR" not in content


def test_a_trait_in_the_general_block_keeps_its_group(
    reference_prompt: Prompt, reference_bindings: dict[str, str]
) -> None:
    """The counterpart: there the group is the only remaining address."""
    prompt = reference_prompt.apply(TraitPatch(changes={"formatting.max_words": 40})).prompt
    prompt = prompt.model_copy(update={"renderer": RendererConfig(format="xml")})
    content = prompt.render(bindings=reference_bindings).messages[0].content
    assert "<general:constraints>\n    FORMATTING max_words = 40" in content


def test_a_dotless_trait_drops_its_synthetic_group(
    reference_prompt: Prompt, reference_bindings: dict[str, str]
) -> None:
    prompt = reference_prompt.model_copy(
        update={"traits": {"language": "de"}, "renderer": RendererConfig(format="markdown")}
    )
    content = prompt.render(bindings=reference_bindings).messages[0].content
    assert content.startswith("## general\n\n- language = de")


def test_keyvalue_keeps_the_group_the_other_formats_drop() -> None:
    """The grammar is the signal here, so the group stays even though the header
    repeats it."""
    prompt = Prompt(
        sections=[Section(key="behavior", content="x")], traits={"behavior.tone": "terse"}
    )
    assert prompt.render().messages[0].content == "#BEHAVIOR\nBEHAVIOR tone = terse\nx"


def _nested_identity(**options: object) -> Prompt:
    return Prompt(
        sections=[
            Section(
                key="identity",
                children=[
                    Section(key="identity.character", content="Du bist Hera."),
                    Section(key="identity.creator", content="Von Lukas erschaffen."),
                ],
            )
        ],
        traits={"identity.tone": "friendly"},
        renderer=RendererConfig(**options),
    )


def test_every_section_carries_its_full_address_by_default() -> None:
    """Nesting becomes a longer address, not an indentation — the grammar stays flat, and
    keyvalue carries as much as the other two formats."""
    content = _nested_identity().render().messages[0].content
    assert content == (
        "#IDENTITY\n"
        "IDENTITY tone = friendly\n"
        "\n"
        "#IDENTITY.CHARACTER\n"
        "Du bist Hera.\n"
        "\n"
        "#IDENTITY.CREATOR\n"
        "Von Lukas erschaffen."
    )


def test_nested_headers_off_shortens_children_into_their_root() -> None:
    """The opt-out, kept because the reference example pins this shape. Children lose
    their key here, which is what would make a format comparison measure address depth
    as much as format."""
    content = _nested_identity(nested_headers=False).render().messages[0].content
    assert content == ("#IDENTITY\nIDENTITY tone = friendly\nDu bist Hera.\nVon Lukas erschaffen.")


def test_a_section_that_only_groups_gets_no_header_of_its_own() -> None:
    """Its name says nothing the children's keys do not already say."""
    prompt = Prompt(
        sections=[
            Section(
                key="behavior",
                children=[
                    Section(
                        key="behavior.style",
                        children=[Section(key="behavior.style.voice", content="Erste Person.")],
                    )
                ],
            )
        ]
    )
    assert prompt.render().messages[0].content == "#BEHAVIOR.STYLE.VOICE\nErste Person."


def test_nested_headers_route_traits_to_the_child_they_name() -> None:
    prompt = _nested_identity().model_copy(update={"traits": {"identity.character.mood": "warm"}})
    content = prompt.render().messages[0].content
    assert "#IDENTITY.CHARACTER\nIDENTITY.CHARACTER mood = warm\nDu bist Hera." in content


def test_nested_headers_honour_constraints_last() -> None:
    prompt = _nested_identity(constraints_first=False).model_copy(
        update={"traits": {"identity.character.mood": "warm"}}
    )
    content = prompt.render().messages[0].content
    assert "#IDENTITY.CHARACTER\nDu bist Hera.\nIDENTITY.CHARACTER mood = warm" in content


def test_nested_headers_leave_the_other_formats_alone() -> None:
    """The option is a keyvalue matter; the other two carry the address anyway."""
    for fmt in ("xml", "markdown"):
        plain = _nested_identity(format=fmt).render().messages[0].content
        off = _nested_identity(format=fmt, nested_headers=False).render().messages[0].content
        assert plain == off


def test_the_trait_address_is_the_same_in_every_format() -> None:
    """Only the separator differs: a dot in keyvalue, a colon in the qualified tag."""
    prompt = Prompt(
        sections=[
            Section(key="behavior", children=[Section(key="behavior.style", content="Kurz.")])
        ],
        traits={"behavior.style.tone": "terse"},
    )
    assert "BEHAVIOR.STYLE tone = terse" in prompt.render().messages[0].content
    xml = prompt.model_copy(update={"renderer": RendererConfig(format="xml")})
    assert "<behavior:style:constraints>\n      tone = terse" in xml.render().messages[0].content


def test_unqualified_xml_output_parses() -> None:
    """Qualified tags are not namespace-declared XML; this is the way out for anything
    that has to parse the result."""
    prompt = Prompt(
        sections=[
            Section(
                key="behavior",
                children=[Section(key="behavior.character", content="a < b")],
            )
        ],
        traits={"behavior.tone": "terse"},
        renderer=RendererConfig(format="xml", qualified_tags=False),
    )
    root = ElementTree.fromstring(prompt.render().messages[0].content)
    assert [child.tag for child in root] == ["constraints", "character"]


def test_trait_with_unknown_prefix_lands_in_the_general_block(
    reference_prompt: Prompt, reference_bindings: dict[str, str]
) -> None:
    prompt = reference_prompt.apply(TraitPatch(changes={"formatting.max_words": 40})).prompt
    content = prompt.render(bindings=reference_bindings).messages[0].content
    assert content.startswith("#GENERAL\nFORMATTING max_words = 40\n\n#IDENTITY")


def test_trait_of_a_disabled_section_lands_in_the_general_block(
    reference_prompt: Prompt, reference_bindings: dict[str, str]
) -> None:
    prompt = reference_prompt.set_enabled("behavior", False)
    content = prompt.render(bindings=reference_bindings).messages[0].content
    assert content.startswith("#GENERAL\nBEHAVIOR hallucinate = never\nBEHAVIOR tone = terse")
    assert "#BEHAVIOR" not in content


def test_trait_without_a_dot_lands_in_the_general_block(
    reference_prompt: Prompt, reference_bindings: dict[str, str]
) -> None:
    prompt = reference_prompt.model_copy(update={"traits": {"language": "de"}})
    content = prompt.render(bindings=reference_bindings).messages[0].content
    assert content.startswith("#GENERAL\nGENERAL language = de")


def test_slot_without_binding_drops_the_section(
    reference_prompt: Prompt, reference_bindings: dict[str, str]
) -> None:
    del reference_bindings["memories"]
    result = reference_prompt.render(bindings=reference_bindings)
    assert result.messages[1].content == "#REQUEST\nWie war das nochmal mit der Ablation?"


def test_required_slot_without_binding_raises(reference_prompt: Prompt) -> None:
    with pytest.raises(MissingBinding):
        reference_prompt.render(bindings={"tools": "x"})


def test_binding_without_slot_is_reported_not_raised(
    reference_prompt: Prompt, reference_bindings: dict[str, str]
) -> None:
    reference_bindings["skills"] = "nichts"
    result = reference_prompt.render(bindings=reference_bindings)
    assert result.unused_bindings == ["skills"]


def test_budget_drops_the_lowest_priority_section_first(
    reference_prompt: Prompt, reference_bindings: dict[str, str]
) -> None:
    full = reference_prompt.render(bindings=reference_bindings)
    budget = TokenBudget(limit=full.snapshot.token_estimate - 1)
    result = reference_prompt.render(bindings=reference_bindings, budget=budget)
    assert result.snapshot.dropped_keys == ["identity"]
    assert "#IDENTITY" not in result.messages[0].content
    assert result.snapshot.token_estimate <= budget.available


def test_budget_reserve_counts_against_the_limit(
    reference_prompt: Prompt, reference_bindings: dict[str, str]
) -> None:
    full = reference_prompt.render(bindings=reference_bindings)
    budget = TokenBudget(limit=full.snapshot.token_estimate, reserve=1)
    result = reference_prompt.render(bindings=reference_bindings, budget=budget)
    assert result.snapshot.dropped_keys == ["identity"]


def test_budget_with_only_required_sections_raises() -> None:
    prompt = Prompt(
        sections=[Section(key="request", role=Role.USER, required=True, content="x" * 400)]
    )
    with pytest.raises(BudgetExceeded):
        prompt.render(budget=TokenBudget(limit=10))


def test_required_descendant_protects_its_parent() -> None:
    prompt = Prompt(
        sections=[
            Section(
                key="request",
                role=Role.USER,
                priority=1,
                children=[Section(key="request.body", required=True, content="x" * 400)],
            )
        ]
    )
    with pytest.raises(BudgetExceeded):
        prompt.render(budget=TokenBudget(limit=10))


def test_fold_into_system_yields_one_system_message(
    reference_prompt: Prompt, reference_bindings: dict[str, str]
) -> None:
    result = reference_prompt.render(bindings=reference_bindings)
    assert [message.role for message in result.messages] == [Role.SYSTEM, Role.USER]


def test_native_developer_role_yields_two_messages(
    reference_prompt: Prompt, reference_bindings: dict[str, str]
) -> None:
    prompt = reference_prompt.model_copy(
        update={"renderer": RendererConfig(developer_role="native")}
    )
    result = prompt.render(bindings=reference_bindings)
    assert [message.role for message in result.messages] == [
        Role.SYSTEM,
        Role.DEVELOPER,
        Role.USER,
    ]
    assert result.messages[0].content.startswith("#IDENTITY")
    assert result.messages[1].content.startswith("#BEHAVIOR")


@pytest.mark.parametrize("value", ["a = b", "zwei\nzeilen"])
def test_keyvalue_rejects_values_that_break_the_grammar(value: str) -> None:
    prompt = Prompt(
        sections=[Section(key="behavior", content="x")], traits={"behavior.tone": value}
    )
    with pytest.raises(TraitError):
        prompt.render()


def test_xml_escapes_angle_brackets_and_ampersands() -> None:
    prompt = Prompt(
        sections=[Section(key="identity", content="a < b & c > d")],
        renderer=RendererConfig(format="xml"),
    )
    content = prompt.render().messages[0].content
    assert "a &lt; b &amp; c &gt; d" in content
    assert content == "<identity>\n  a &lt; b &amp; c &gt; d\n</identity>"


def test_xml_escapes_bound_slot_content() -> None:
    prompt = Prompt(
        sections=[Section(key="tools", slot="tools")],
        renderer=RendererConfig(format="xml"),
    )
    content = prompt.render(bindings={"tools": "<call/>"}).messages[0].content
    assert "&lt;call/&gt;" in content


def test_xml_renders_an_empty_binding_as_an_empty_element() -> None:
    prompt = Prompt(
        sections=[Section(key="tools", slot="tools")],
        renderer=RendererConfig(format="xml"),
    )
    assert prompt.render(bindings={"tools": ""}).messages[0].content == "<tools></tools>"


def test_xml_without_qualified_tags_uses_the_leaf_key() -> None:
    prompt = Prompt(
        sections=[
            Section(key="behavior", children=[Section(key="behavior.character", content="x")])
        ],
        traits={"behavior.tone": "terse"},
        renderer=RendererConfig(format="xml", qualified_tags=False),
    )
    content = prompt.render().messages[0].content
    assert "<character>" in content
    assert "<constraints>" in content
    assert "behavior:" not in content


def test_constraints_last(reference_prompt: Prompt, reference_bindings: dict[str, str]) -> None:
    """Ordering inside one block, so with the children folded in."""
    prompt = reference_prompt.model_copy(
        update={"renderer": RendererConfig(constraints_first=False, nested_headers=False)}
    )
    content = prompt.render(bindings=reference_bindings).messages[0].content
    assert "#BEHAVIOR\nDu hast eine Meinung" in content
    assert content.index("BEHAVIOR tone") > content.index("Du hast eine Meinung")


def test_markdown_renders_headings_and_bullets(
    reference_prompt: Prompt,
    reference_registry: TraitRegistry,
    reference_bindings: dict[str, str],
) -> None:
    prompt = reference_prompt.model_copy(update={"renderer": RendererConfig(format="markdown")})
    content = (
        prompt.render(bindings=reference_bindings, registry=reference_registry).messages[0].content
    )
    assert content.startswith("## identity\n\nDu bist Hera")
    assert "- Antworte knapp. Kein Vorspann, kein Nachklang." in content
    assert "### behavior.character" in content


def test_trait_group_separator_is_configurable() -> None:
    prompt = Prompt(
        sections=[Section(key="behavior", content="x")],
        traits={"behavior.tone": "terse"},
        renderer=RendererConfig(trait_group_separator="."),
    )
    assert "BEHAVIOR.tone = terse" in prompt.render().messages[0].content


def test_title_replaces_the_key_in_the_header() -> None:
    prompt = Prompt(sections=[Section(key="identity", title="wer du bist", content="x")])
    assert prompt.render().messages[0].content.startswith("#WER DU BIST")


def test_snapshot_records_what_the_rendering_came_from(
    reference_prompt: Prompt,
    reference_registry: TraitRegistry,
    reference_bindings: dict[str, str],
) -> None:
    result = reference_prompt.render(bindings=reference_bindings, registry=reference_registry)
    snapshot = result.snapshot
    assert snapshot.prompt_fingerprint == reference_prompt.fingerprint()
    assert snapshot.registry_fingerprint == reference_registry.fingerprint()
    assert snapshot.renderer == reference_prompt.renderer
    assert snapshot.traits == reference_prompt.traits
    assert snapshot.dropped_keys == []
    assert snapshot.token_estimate > 0
    assert snapshot.component_versions == {}


def test_snapshot_without_registry_has_no_registry_fingerprint(
    reference_prompt: Prompt, reference_bindings: dict[str, str]
) -> None:
    """Without a registry the output is determined by the prompt alone."""
    result = reference_prompt.render(bindings=reference_bindings)
    assert result.snapshot.registry_fingerprint is None


def test_snapshot_tells_two_registry_orders_apart(
    reference_prompt: Prompt,
    reference_registry: TraitRegistry,
    reference_bindings: dict[str, str],
) -> None:
    """Different declaration order, different rendering — so the recorded origin has to
    differ as well."""
    shuffled = TraitRegistry(specs=list(reversed(reference_registry.specs)))
    first = reference_prompt.render(bindings=reference_bindings, registry=reference_registry)
    second = reference_prompt.render(bindings=reference_bindings, registry=shuffled)
    assert first.messages != second.messages
    assert first.snapshot.registry_fingerprint is not None
    assert second.snapshot.registry_fingerprint is not None
    assert first.snapshot.registry_fingerprint != second.snapshot.registry_fingerprint


def test_snapshot_lists_unbound_slots(
    reference_prompt: Prompt, reference_bindings: dict[str, str]
) -> None:
    """Three causes for missing content, three fields."""
    del reference_bindings["memories"]
    reference_bindings["skills"] = "nichts"
    full = reference_prompt.render(bindings=dict(reference_bindings))
    budget = TokenBudget(limit=full.snapshot.token_estimate - 1)
    result = reference_prompt.render(bindings=reference_bindings, budget=budget)
    assert result.snapshot.unbound_slots == ["memories"]
    assert result.snapshot.dropped_keys == ["identity"]
    assert result.unused_bindings == ["skills"]


def test_declared_order_beats_key_order_for_traits() -> None:
    """The registry declares the order; without a registry the key decides."""
    prompt = Prompt(
        sections=[Section(key="behavior", content="x")],
        traits={"behavior.tone": "terse", "behavior.hallucinate": "never"},
    )
    registry = TraitRegistry(
        specs=[
            TraitSpec(key="behavior.tone", type="str"),
            TraitSpec(key="behavior.hallucinate", type="str"),
        ]
    )
    with_registry = prompt.render(registry=registry).messages[0].content
    without_registry = prompt.render().messages[0].content
    assert with_registry.index("tone") < with_registry.index("hallucinate")
    assert without_registry.index("hallucinate") < without_registry.index("tone")


def test_empty_prompt_renders_no_messages() -> None:
    result = Prompt().render()
    assert result.messages == []
    assert result.snapshot.token_estimate == 0


def test_container_without_surviving_children_is_left_out() -> None:
    prompt = Prompt(
        sections=[
            Section(key="behavior", children=[Section(key="behavior.tools", slot="tools")]),
            Section(key="identity", content="x"),
        ]
    )
    assert prompt.render().messages[0].content == "#IDENTITY\nx"
