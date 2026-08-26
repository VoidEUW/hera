"""The key-value renderer: ``#SECTION`` headers and ``GROUP name = value`` lines.

Simple grammar over nesting — the small local models this library targets read it more
reliably than markup. Trait templates are ignored on purpose here: this grammar is
itself the signal.

Every section renders under its full key, so nesting shows up as a longer address rather
than as indentation and the grammar stays flat. That is what keeps the three formats
comparable: ``RendererConfig.nested_headers=False`` gives the shortened form of the
reference example, in which ``behavior.character`` and ``behavior.creator`` become two
adjacent paragraphs under ``#BEHAVIOR`` and are no longer told apart — keyvalue then
carries less than xml and markdown, and a comparison between the formats measures
address depth as much as format.
"""

from __future__ import annotations

from hera_prompts.errors import TraitError
from hera_prompts.models import RendererConfig
from hera_prompts.render.base import Block, TraitLine
from hera_prompts.traits import format_value


class KeyValueRenderer:
    """Renders blocks as a flat, uppercase key-value grammar."""

    block_separator = "\n\n"

    def block(self, block: Block, config: RendererConfig, depth: int = 0) -> str:
        """One header line, then traits and text.

        With ``nested_headers`` every section gets its own header under its full key and
        the result stays flat — nesting becomes visible as a longer address, not as
        indentation. Without it, children contribute their lines under the header of
        their top-level section.
        """
        if not config.nested_headers:
            return "\n".join([f"#{block.title.upper()}", *self._body(block, config)])
        body = self._own_body(block, config)
        parts: list[str] = []
        if body or not block.children:
            # A section that only groups others contributes nothing but its own name, and
            # the children already carry it in their keys.
            parts.append("\n".join([f"#{block.title.upper()}", *body]))
        parts.extend(self.block(child, config, depth + 1) for child in block.children)
        return self.block_separator.join(parts)

    def _body(self, block: Block, config: RendererConfig) -> list[str]:
        traits = [self._trait(trait, config) for trait in block.traits]
        text: list[str] = []
        if block.text is not None:
            text.append(block.text)
        for child in block.children:
            text.extend(self._body(child, config))
        if config.constraints_first:
            return traits + text
        return text + traits

    def _own_body(self, block: Block, config: RendererConfig) -> list[str]:
        traits = [self._trait(trait, config) for trait in block.traits]
        text = [block.text] if block.text is not None else []
        if config.constraints_first:
            return traits + text
        return text + traits

    def _trait(self, trait: TraitLine, config: RendererConfig) -> str:
        value = format_value(trait.value)
        if "\n" in value or "=" in value:
            raise TraitError(
                f"trait {trait.key!r} carries a value that breaks the keyvalue grammar: {value!r}"
            )
        return trait.raw(config.trait_group_separator)
