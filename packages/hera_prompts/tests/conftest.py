"""Fixtures for the reference example pinned down in CLAUDE.md."""

from __future__ import annotations

import pytest

from hera_prompts import (
    Prompt,
    RendererConfig,
    Role,
    Section,
    TraitRegistry,
    TraitSpec,
)


@pytest.fixture
def reference_registry() -> TraitRegistry:
    return TraitRegistry(
        specs=[
            TraitSpec(
                key="behavior.tone",
                type="str",
                description="How much prose the answer may spend.",
                choices=["terse", "ample"],
                render={"terse": "Antworte knapp. Kein Vorspann, kein Nachklang."},
            ),
            TraitSpec(
                key="behavior.hallucinate",
                type="str",
                description="What to do when knowledge runs out.",
                choices=["never", "flag"],
                render={"never": "Erfinde nichts. Wenn du etwas nicht weißt, sag es."},
            ),
        ]
    )


@pytest.fixture
def reference_prompt() -> Prompt:
    return Prompt(
        sections=[
            Section(
                key="identity",
                role=Role.SYSTEM,
                locked=True,
                priority=10,
                content="Du bist Hera, eine aufmerksame Assistentin mit eigenem Kopf.",
            ),
            Section(
                key="behavior",
                role=Role.DEVELOPER,
                priority=50,
                children=[
                    Section(
                        key="behavior.character",
                        role=Role.DEVELOPER,
                        priority=50,
                        content=(
                            "Du hast eine Meinung und sagst sie. Bei Unsicherheit sagst du das."
                        ),
                    )
                ],
            ),
            Section(key="tools", role=Role.DEVELOPER, slot="tools", locked=True, priority=30),
            Section(key="memories", role=Role.USER, slot="memories", priority=20),
            Section(key="request", role=Role.USER, slot="request", required=True, priority=100),
        ],
        traits={"behavior.tone": "terse", "behavior.hallucinate": "never"},
        renderer=RendererConfig(format="keyvalue", constraints_first=True),
    )


@pytest.fixture
def reference_bindings() -> dict[str, str]:
    return {
        "tools": "CALL search(query=~~QUERY~~)",
        "memories": "MEMORY city = Chemnitz",
        "request": "Wie war das nochmal mit der Ablation?",
    }
