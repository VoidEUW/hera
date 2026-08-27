"""The XML renderer: one element per section, traits as a ``constraints`` element.

Unlike the key-value renderer this one uses the ``render`` templates of the registry, so
the same trait appears once as a raw pair and once as a full sentence.

``qualified_tags=True`` produces XML-*shaped* text, not well-formed XML: a colon in a
tag name is a namespace prefix and would have to be declared with ``xmlns:``. The spec
pins this shape because it is what the model reads, and nothing here parses its own
output. Anything that does have to parse it — a validator, a comparison tool — should
render with ``qualified_tags=False``, which nests plain tag names and parses.
"""

from __future__ import annotations

from hera_prompts.models import RendererConfig
from hera_prompts.render.base import Block

INDENT = "  "
CONSTRAINTS = "constraints"


def escape(text: str) -> str:
    """Escape the three characters that would otherwise break the markup."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class XmlRenderer:
    """Renders blocks as nested elements with optionally qualified tags."""

    block_separator = "\n"

    def block(self, block: Block, config: RendererConfig, depth: int = 0) -> str:
        tag = self._tag(block, config)
        indent = INDENT * depth
        traits = self._constraints(block, config, depth + 1)
        body: list[str] = []
        if block.text is not None:
            # A block built from the general trait bin has no section behind it and is always
            # this library's own text, so escaping is the safe default there.
            protect = block.section.escape if block.section is not None else True
            body.extend(
                f"{INDENT * (depth + 1)}{escape(line) if protect else line}"
                for line in block.text.splitlines()
            )
        for child in block.children:
            body.append(self.block(child, config, depth + 1))
        if traits is not None:
            body = [traits, *body] if config.constraints_first else [*body, traits]
        if not body:
            return f"{indent}<{tag}></{tag}>"
        return "\n".join([f"{indent}<{tag}>", *body, f"{indent}</{tag}>"])

    def _constraints(self, block: Block, config: RendererConfig, depth: int) -> str | None:
        if not block.traits:
            return None
        indent = INDENT * depth
        tag = (
            f"{block.key.replace('.', ':')}:{CONSTRAINTS}" if config.qualified_tags else CONSTRAINTS
        )
        lines = [
            f"{indent}{INDENT}{escape(trait.sentence(config.trait_group_separator, block.key))}"
            for trait in block.traits
        ]
        return "\n".join([f"{indent}<{tag}>", *lines, f"{indent}</{tag}>"])

    def _tag(self, block: Block, config: RendererConfig) -> str:
        return block.key.replace(".", ":") if config.qualified_tags else block.leaf_key
