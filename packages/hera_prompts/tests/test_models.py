"""Section validation happens on construction, not at render time."""

from __future__ import annotations

import pytest

from hera_prompts import Message, Role, Section, SectionError


def test_child_key_without_parent_prefix_raises() -> None:
    with pytest.raises(SectionError):
        Section(key="behavior", children=[Section(key="character", content="x")])


@pytest.mark.parametrize("key", ["Behavior", "1behavior", "behavior.", ".behavior", "be-havior"])
def test_invalid_key_raises(key: str) -> None:
    with pytest.raises(SectionError):
        Section(key=key)


def test_duplicate_key_in_subtree_raises() -> None:
    with pytest.raises(SectionError):
        Section(
            key="behavior",
            children=[
                Section(key="behavior.character", content="a"),
                Section(key="behavior.character", content="b"),
            ],
        )


def test_content_and_slot_are_mutually_exclusive() -> None:
    with pytest.raises(SectionError):
        Section(key="tools", content="x", slot="tools")


def test_section_with_children_carries_neither_content_nor_slot() -> None:
    with pytest.raises(SectionError):
        Section(key="behavior", content="x", children=[Section(key="behavior.character")])


def test_child_inherits_the_role_of_its_subtree() -> None:
    section = Section(
        key="behavior",
        role=Role.DEVELOPER,
        children=[
            Section(
                key="behavior.style",
                children=[Section(key="behavior.style.voice", content="x")],
            )
        ],
    )
    assert [node.role for node in section.walk()] == [Role.DEVELOPER] * 3


def test_child_with_a_deviating_explicit_role_raises() -> None:
    """Only the role of a top level section is evaluated, so a deviating one below it
    would be silently ineffective."""
    with pytest.raises(SectionError):
        Section(
            key="behavior",
            role=Role.DEVELOPER,
            children=[Section(key="behavior.character", role=Role.USER, content="x")],
        )


def test_inherited_roles_survive_a_round_trip() -> None:
    section = Section(
        key="behavior",
        role=Role.DEVELOPER,
        children=[Section(key="behavior.character", content="x")],
    )
    assert Section.model_validate_json(section.model_dump_json()) == section


def test_walk_yields_document_order() -> None:
    section = Section(
        key="behavior",
        children=[
            Section(key="behavior.character", content="a"),
            Section(
                key="behavior.style",
                children=[Section(key="behavior.style.voice", content="b")],
            ),
        ],
    )
    assert [node.key for node in section.walk()] == [
        "behavior",
        "behavior.character",
        "behavior.style",
        "behavior.style.voice",
    ]


def test_message_dump_is_the_wire_shape() -> None:
    assert Message(role=Role.SYSTEM, content="hi").model_dump() == {
        "role": "system",
        "content": "hi",
    }
