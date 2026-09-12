"""Known request options for models that need one, so nobody has to know the incantation.

A model registered on an endpoint may carry ``options`` — request-body fields that server
understands and Hera does not (``ModelEntry.options``). That seam is deliberately schema-free,
which makes it capable of anything and discoverable by nobody: *set*
``chat_template_kwargs.clear_thinking = false`` is not something a person finds by looking at a
settings screen.

So the two that are known are written down here, offered on that screen, and **picked** rather
than matched. Nothing in Hera looks at a model id and decides what it is: `glm-4.7-flash`,
`GLM-4.7-Flash-Q4_K_M` and `zai/glm-4.7` are the same weights under three names, an id is a
string somebody typed, and guessing wrong here means silently sending a flag to a server that
rejects the whole request. It is the same stance ``ProviderKind`` takes about ``base_url``, for
the same reason.

A preset is a starting point, not a mode. What it does is fill the editor; what is stored is
the resulting options, and they can be edited afterwards like anything else typed in by hand.
Nothing records which preset they came from, because a preset that a later version of Hera
changed under an install would be a setting that changed without anybody touching it.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

__all__ = ["PRESETS", "ModelPreset"]


class ModelPreset(BaseModel):
    """One named set of request options, offered on Settings → Models."""

    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    hint: str
    """One sentence about what the options are for. Shown beside the choice, because a person
    picking a preset for a model they just installed is exactly the person who has no idea what
    ``clear_thinking`` means."""

    options: dict[str, Any]


PRESETS: tuple[ModelPreset, ...] = (
    ModelPreset(
        id="glm-4.7",
        label="GLM-4.7",
        hint=(
            "Keeps the reasoning of earlier turns when the history is rendered. Without it "
            "GLM-4.7 re-reads a multi-turn conversation as if it had just started."
        ),
        options={"chat_template_kwargs": {"enable_thinking": True, "clear_thinking": False}},
    ),
    ModelPreset(
        id="gpt-oss",
        label="GPT-OSS",
        hint="How long gpt-oss deliberates before it answers — low, medium or high.",
        options={"reasoning_effort": "medium"},
    ),
)
"""Every preset, in the order they are offered.

Two, and both of them are here because a real endpoint needed them (issue #63). This list is
not meant to grow into a catalogue of every OpenAI-compatible server's flags — anything that is
not here is typed into the same field by hand, which is the supported path and always was.
"""
