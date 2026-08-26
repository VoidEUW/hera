"""The markdown renderer: headings per section, traits as a bullet list.

Like the XML renderer it uses the ``render`` templates of the registry.
"""

from __future__ import annotations

from hera_prompts.models import RendererConfig
from hera_prompts.render.base import Block


class MarkdownRenderer:
    """Renders blocks as headings with prose underneath."""

    block_separator = "\n\n"

    def block(self, block: Block, config: RendererConfig, depth: int = 0) -> str:
        parts = [f"{'#' * (depth + 2)} {block.title}"]
        traits = (
            [
                "\n".join(
                    f"- {t.sentence(config.trait_group_separator, block.key)}" for t in block.traits
                )
            ]
            if block.traits
            else []
        )
        body: list[str] = []
        if block.text is not None:
            body.append(block.text)
        body.extend(self.block(child, config, depth + 1) for child in block.children)
        parts.extend(traits + body if config.constraints_first else body + traits)
        return "\n\n".join(parts)
