"""Core value objects: roles, messages, sections and the renderer configuration."""

from __future__ import annotations

import re
from collections.abc import Iterator
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hera_prompts.errors import SectionError

KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")


class Role(StrEnum):
    """The three roles this library knows. Mapping them onto a concrete provider
    format is the job of the layer above."""

    SYSTEM = "system"
    DEVELOPER = "developer"
    USER = "user"


class Message(BaseModel):
    """One rendered message. ``model_dump()`` already yields the wire shape."""

    model_config = ConfigDict(frozen=True)

    role: Role
    content: str


class RendererConfig(BaseModel):
    """Rendering options. They live *inside* the prompt so that a stored variant is
    fully described by the object alone."""

    model_config = ConfigDict(frozen=True)

    format: Literal["keyvalue", "xml", "markdown"] = "keyvalue"
    qualified_tags: bool = True
    constraints_first: bool = True
    developer_role: Literal["fold_into_system", "native"] = "fold_into_system"
    trait_group_separator: str = " "
    nested_headers: bool = True
    """Whether ``keyvalue`` gives nested sections a header of their own.

    Only this format has a choice here — ``xml`` and ``markdown`` carry the address in
    their tags and headings anyway, and ignore the option. On by default, so all three
    formats carry the same information: without it a nested section loses its key and
    keyvalue would come out of any comparison worse for a reason that has nothing to do
    with the format. Turn it off to get the shortened form of the reference example, in
    which children contribute their text under the header of their top-level section.
    """


class Section(BaseModel):
    """A node of the prompt tree.

    Structure is generated and validated on construction, never typed by hand. A
    section either holds authored ``content``, refers to a ``slot``, or has
    ``children`` — never a combination of those.
    """

    model_config = ConfigDict(frozen=True)

    key: str
    title: str | None = None
    content: str | None = None
    slot: str | None = None
    children: list[Section] = Field(default_factory=list)
    role: Role = Role.SYSTEM
    priority: int = 100
    required: bool = False
    locked: bool = False
    enabled: bool = True

    @model_validator(mode="after")
    def _validate_subtree(self) -> Section:
        if not KEY_PATTERN.match(self.key):
            raise SectionError(f"invalid section key: {self.key!r}")
        if self.content is not None and self.slot is not None:
            raise SectionError(f"section {self.key!r} sets both content and slot")
        if self.children and (self.content is not None or self.slot is not None):
            raise SectionError(f"section {self.key!r} has children as well as content or slot")

        seen = {self.key}
        for child in self.children:
            if not child.key.startswith(f"{self.key}."):
                raise SectionError(
                    f"child key {child.key!r} is not prefixed with {self.key!r} plus a dot"
                )
            for node in child.walk():
                if node.key in seen:
                    raise SectionError(f"duplicate section key: {node.key!r}")
                seen.add(node.key)

        children = [_aligned_role(child, self.role) for child in self.children]
        if children != self.children:
            # Assigning through __dict__ is the way to adjust a frozen model from its own
            # validator; returning a copy is ignored when the model is built via __init__.
            self.__dict__["children"] = children
        return self

    def walk(self) -> Iterator[Section]:
        """Yield this section and all of its descendants in document order."""
        yield self
        for child in self.children:
            yield from child.walk()


def _aligned_role(section: Section, role: Role) -> Section:
    """Carry the role of a subtree down into it.

    Only the role of a top level section is evaluated, so a child that sets a different
    one would be silently ignored — exactly the kind of quietly ineffective field this
    library removes elsewhere. Setting it explicitly and differently is therefore an
    error; leaving it alone inherits, which also keeps the field honest once the section
    has been through a serialisation round trip.
    """
    if "role" in section.model_fields_set:
        if section.role is not role:
            raise SectionError(
                f"section {section.key!r} sets role {section.role.value!r}, but its subtree "
                f"is rendered as {role.value!r}"
            )
        return section
    children = [_aligned_role(child, role) for child in section.children]
    if section.role is role and children == section.children:
        return section
    return section.model_copy(update={"role": role, "children": children})
