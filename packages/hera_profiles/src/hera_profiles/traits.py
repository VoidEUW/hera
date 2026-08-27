"""Behaviour traits: the scalar half of a profile.

A mind region is prose she reads. A trait is a **setting** — one key, one small value, with a
declared type and a declared set of admissible values. The split matters because the two want
completely different editors and completely different validation: "how formal should she be"
is a dropdown with three options that can be checked, and "what is her character" is a
textarea that cannot.

Trait keys are dotted, and the prefix is a section key from
:data:`hera_profiles.builder.SKELETON`. ``hera_prompts`` routes a trait into the block whose
key matches that prefix, so ``identity.tone.formality`` renders inside ``<identity:tone>``
rather than in a settings dump at the top. A trait whose prefix names no section still
renders, in a general block — which is the failure mode to watch for when adding one.

``allow_unknown=False`` is deliberate. A profile's traits come from a stored JSON column, and
a key that no longer exists — renamed in a later version, or mistyped by hand — should be
reported by :meth:`hera_prompts.Prompt.check` rather than silently rendered as a stray line in
the system prompt. Regions are the place to say something the registry did not anticipate.
"""

from __future__ import annotations

from hera_prompts import TraitRegistry, TraitSpec

LANGUAGE = "identity.language"
FORMALITY = "identity.tone.formality"
EMOJI = "identity.tone.emoji"
DEPTH = "approach.depth"

BEHAVIOUR_TRAITS = TraitRegistry(
    allow_unknown=False,
    specs=[
        TraitSpec(
            key=LANGUAGE,
            type="str",
            default="English",
            description="The language she answers in.",
            render="You answer in {value}, whatever language the question was asked in.",
        ),
        TraitSpec(
            key=FORMALITY,
            type="str",
            default="neutral",
            choices=["casual", "neutral", "formal"],
            description="Register.",
            render={
                "casual": "You speak casually, the way you would to someone you know well.",
                "neutral": "You speak plainly — neither stiff nor chatty.",
                "formal": "You keep a formal register.",
            },
        ),
        TraitSpec(
            key=EMOJI,
            type="bool",
            default=False,
            description="Whether emoji may appear in her prose.",
            render={
                "true": "Emoji are welcome where they carry meaning.",
                "false": "Do not use emoji.",
            },
        ),
        TraitSpec(
            key=DEPTH,
            type="str",
            default="normal",
            choices=["brief", "normal", "thorough"],
            description="How much work an answer gets before it is good enough.",
            render={
                "brief": "Answer in as few words as the question honestly needs.",
                "normal": "Give a complete answer without padding it.",
                "thorough": "Work the problem properly and show the reasoning that matters.",
            },
        ),
    ],
)
"""The declared traits, in the order they render.

Order is part of the registry's fingerprint because it is part of the output — see
:meth:`hera_prompts.TraitRegistry.fingerprint`.
"""
